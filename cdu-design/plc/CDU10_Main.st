(* =============================================================================
   CDU-10  10 kW liquid-to-liquid CDU  --  PLC program, Rev B
   IEC 61131-3 Structured Text, CODESYS 3.5 dialect.
   Cyclic task: 100 ms.  Hardware watchdog: 500 ms (drops the load-permit relay).

   This program implements calc/cdu_control.py block for block.  That Python
   module is the executable specification; it was tuned and verified against
   the plant model in calc/cdu_sim.py (results in sim/results.md).  Any change
   here is made there first and re-simulated.

   Units: C, bar g (pressure transmitters), kPa (differential), L/min, %.
   ============================================================================= *)

TYPE E_State : (ST_OFF := 0, ST_STARTING := 1, ST_RUNNING := 2, ST_TRIPPED := 3); END_TYPE

(* Trip bits, latched until reset.  Bit numbers are the Modbus trip word bits. *)
TYPE E_Trip : (TR_LOW_FLOW := 0, TR_HIGH_TEMP := 1, TR_LOW_STATIC := 2, TR_HIGH_DISCH := 3,
               TR_LEAK_TRAY := 4, TR_INVENTORY := 5, TR_FWS_LOST := 6, TR_SENSOR := 7,
               TR_START_FAIL := 8, TR_REMOTE_STOP := 9); END_TYPE

(* Alarm bits, non-latching. *)
TYPE E_Alarm : (AL_SENSOR := 0, AL_LOW_FLOW := 1, AL_HIGH_TEMP := 2, AL_DEW := 3, AL_INVENTORY := 4,
                AL_HIGH_DISCH := 5, AL_FILTER := 6, AL_LEAK_HOSE := 7, AL_FWS_LOST := 8); END_TYPE

(* ----------------------------------------------------------------------------- *)
VAR_GLOBAL
    (* ---- analogue inputs, scaled to engineering units by the I/O layer ---- *)
    TT101 : REAL;   (* TCS supply, C *)
    TT102 : REAL;   (* TCS return (mixed, after bypass tee), C *)
    TT201 : REAL;   (* facility supply, C *)
    TT202 : REAL;   (* facility return, C *)
    PT101 : REAL;   (* pump suction / static, bar g *)
    PT102 : REAL;   (* pump discharge, bar g *)
    PT103 : REAL;   (* TCS supply after FT-101, bar g *)
    PT201 : REAL;   (* facility supply, bar g *)
    PT202 : REAL;   (* facility return, bar g *)
    PDT101 : REAL;  (* filter differential, kPa *)
    FT101 : REAL;   (* TCS total flow, L/min *)
    FT201 : REAL;   (* facility flow, L/min *)
    AT301_T : REAL; (* room temperature, C *)
    AT301_RH : REAL;(* room relative humidity, % *)
    ZT201 : REAL;   (* control valve position feedback, % *)
    (* ---- digital inputs ---- *)
    LDS301 : BOOL;  (* drip-tray leak *)
    LDS302 : BOOL;  (* hose-end leak *)
    DI_REMOTE_STOP : BOOL;  (* hardwired, normally closed: FALSE = stop *)
    DI_DRIVE_FAULT : BOOL;
    HMI_START, HMI_STOP, HMI_RESET, HMI_INV_ZERO : BOOL;
    (* ---- outputs ---- *)
    AO_PUMP_SPEED : REAL;   (* % to drive *)
    DO_PUMP_RUN : BOOL;
    AO_TCV201 : REAL;       (* % to control valve *)
    DO_XV201_OPEN : BOOL;   (* energise = open; spring closes *)
    DO_LOAD_PERMIT : BOOL;  (* drives the permit relay coil, in series with the watchdog *)
    DO_HORN : BOOL;
END_VAR

(* ---- parameters: retained, writable from the HMI (Modbus write disabled by default) ---- *)
VAR_GLOBAL RETAIN PERSISTENT
    P_SP_T : REAL := 32.0;          P_DEW_MARGIN : REAL := 3.0;
    P_SP_T_MIN : REAL := 25.0;      P_SP_T_MAX : REAL := 40.0;
    P_DP_SP : REAL := 70.0;
    P_SPEED_MIN : REAL := 30.0;     P_SPEED_MAX : REAL := 85.0;   (* 85 % cap: decision D-11 *)
    P_VALVE_MIN_RUN : REAL := 5.0;  P_VALVE_START : REAL := 30.0;
    P_F_EXP : REAL := 29.0;         P_F_MIN : REAL := 27.0;       (* set for the connected servers *)
    P_T_SERVER_MAX : REAL := 40.0;
    P_FWS_TRIP_S : REAL := 20.0;    P_LOW_FLOW_TRIP_S : REAL := 3.0;
    P_V_SYS : REAL := 21.0;         P_V_TANK : REAL := 8.0;
    P_P_PRE : REAL := 0.8;          P_BETA : REAL := 0.00045;
    P_VTW_REF : REAL := 0.79;       P_T_REF : REAL := 15.0;       (* captured by HMI_INV_ZERO *)
    P_INV_WARN_L : REAL := 0.25;    P_INV_TRIP_L : REAL := 0.60;
    P_T_KP : REAL := 8.0;           P_T_TI : REAL := 60.0;
    P_T_IBAND : REAL := 2.0;        P_T_EDB : REAL := 0.05;
    P_FF_ENABLE : BOOL := TRUE;     P_FF_TF : REAL := 10.0;
    P_VALVE_DB : REAL := 0.3;
    P_DP_KP : REAL := 0.4;          P_DP_TI : REAL := 4.0;
    P_FL_KP : REAL := 2.0;          P_FL_TI : REAL := 4.0;
    (* facility circuit, for the feed-forward *)
    P_CV_MAX : REAL := 4.7;         P_RANGEABILITY : REAL := 50.0;
    P_K_FIXED_KPA : REAL := 24.2;   (* facility branch drop excluding TCV, kPa at 24 L/min *)
END_VAR

(* =============================================================================
   PI controller.  Two anti-windup modes:
   - Conditional integration (valve loop): integrator frozen while saturated in
     the direction of the error, while |error| > IBand, or while the actuator
     feedback lags the command.  Leaves the feed-forward intact (see sim notes).
   - Back-calculation tracking (pump loops): integrator pulled toward the
     output actually applied after the max-selector.
   ============================================================================= *)
FUNCTION_BLOCK FB_PI
VAR_INPUT
    Error : REAL;  Bias : REAL;  Kp : REAL;  Ti : REAL;
    OutMin : REAL; OutMax : REAL;
    Dt : REAL := 0.1;
    Conditional : BOOL;           (* TRUE: conditional integration; FALSE: tracking *)
    IBand : REAL := 1.0E9;
    Feedback : REAL;  UseFeedback : BOOL;  LagBand : REAL := 5.0;
    Applied : REAL;               (* tracking mode: output after selector *)
    Preset : BOOL;  PresetValue : REAL;
END_VAR
VAR_OUTPUT
    Out : REAL;
END_VAR
VAR
    I : REAL;  URaw : REAL;  bSat : BOOL;  bLag : BOOL;
END_VAR
    IF Preset THEN
        I := PresetValue - Bias;
    END_IF
    URaw := Kp * Error + I + Bias;
    Out := LIMIT(OutMin, URaw, OutMax);
    IF Conditional THEN
        bSat := (URaw >= OutMax AND Error > 0.0) OR (URaw <= OutMin AND Error < 0.0) OR (ABS(Error) > IBand);
        bLag := UseFeedback AND (ABS(Out - Feedback) > LagBand) AND ((Out - Feedback) * Error > 0.0);
        IF NOT (bSat OR bLag) THEN
            I := LIMIT(-100.0, I + Dt * Kp * Error / Ti, 100.0);
        END_IF
    ELSE
        I := I + Dt * (Kp * Error / Ti + (Applied - URaw) / Ti);
    END_IF
END_FUNCTION_BLOCK

(* ----------------------------------------------------------------------------- *)
FUNCTION F_DewPoint : REAL      (* Magnus formula, 0-60 C *)
VAR_INPUT T : REAL; RH : REAL; END_VAR
VAR g : REAL; END_VAR
    g := LN(MAX(RH, 1.0) / 100.0) + 17.62 * T / (243.12 + T);
    F_DewPoint := 243.12 * g / (17.62 - g);
END_FUNCTION

FUNCTION F_ValvePosForFlow : REAL   (* inverse of the installed equal-percentage valve *)
VAR_INPUT Flow : REAL; DpAvail : REAL; END_VAR
VAR dpFixed, dpV, cvReq, x : REAL; END_VAR
    IF Flow <= 0.0 THEN F_ValvePosForFlow := 0.0; RETURN; END_IF
    dpFixed := P_K_FIXED_KPA * (Flow / 24.0) * (Flow / 24.0);
    dpV := DpAvail - dpFixed;
    IF dpV <= 0.1 THEN F_ValvePosForFlow := 100.0; RETURN; END_IF
    cvReq := (Flow / 3.785) / SQRT(dpV / 6.89476);
    IF cvReq >= P_CV_MAX THEN F_ValvePosForFlow := 100.0; RETURN; END_IF
    x := 1.0 + LN(cvReq / P_CV_MAX) / LN(P_RANGEABILITY);
    F_ValvePosForFlow := LIMIT(5.0, x * 100.0, 100.0);
END_FUNCTION

(* =============================================================================
   Main program
   ============================================================================= *)
PROGRAM PRG_CDU10
VAR
    State : E_State := ST_OFF;
    TripWord : WORD;          (* latched trips, bit = E_Trip *)
    AlarmWord : WORD;         (* live alarms, bit = E_Alarm *)
    tState, tTrip : REAL;     (* s in state / since first trip *)
    DT : REAL := 0.1;

    SpEff, Dew, TripLevel, DpMeas, FwsDp : REAL;
    TMean, VtwMeas, VtwExp, InvDeficit : REAL;
    Q, DtFws, FReq, FfRaw, Ff, E : REAL;
    Speed, Valve, U, UDp, UFl : REAL;
    PumpRun, XvOpen, Permit, HoldValve, CloseXv, SensorBad, FwsBad : BOOL;
    StopAfter : REAL;
    PresetLoops : BOOL;

    piValve, piDp, piFlow : FB_PI;
    tonLfWarn, tonLfTrip, tonHtWarn, tonHtTrip, tonRunOk, tonFwsWarn, tonFwsTrip,
    tonInvWarn, tonInvTrip : TON;
    rtStart, rtReset, rtInvZero : R_TRIG;
END_VAR

    (* ------------------------------------------------------------ derived values *)
    tState := tState + DT;
    tTrip := tTrip + DT;
    Dew := F_DewPoint(AT301_T, AT301_RH);
    SpEff := LIMIT(P_SP_T_MIN, MAX(P_SP_T, Dew + P_DEW_MARGIN), P_SP_T_MAX);
    TripLevel := P_T_SERVER_MAX - 2.0;
    DpMeas := (PT103 - PT101) * 100.0;
    FwsDp := (PT201 - PT202) * 100.0;
    rtStart(CLK := HMI_START);  rtReset(CLK := HMI_RESET);  rtInvZero(CLK := HMI_INV_ZERO);
    PresetLoops := FALSE;

    (* coolant inventory zero: press after every fill, with the loop cold and still *)
    IF rtInvZero.Q AND NOT PumpRun THEN
        P_VTW_REF := P_V_TANK * (1.0 - (P_P_PRE + 1.013) / MAX(PT101 + 1.013, 0.2));
        P_T_REF := 0.5 * (TT101 + TT102);
    END_IF

    (* ------------------------------------------------------------ alarms and trips *)
    AlarmWord := 0;
    SensorBad := (TT101 <= 0.0) OR (TT101 >= 100.0) OR (PT101 <= -1.0) OR (PT101 >= 6.0) OR (FT101 < -1.0);
    IF SensorBad THEN AlarmWord.AL_SENSOR := TRUE; END_IF

    tonLfWarn(IN := (State = ST_RUNNING OR State = ST_TRIPPED) AND PumpRun AND FT101 < 0.8 * P_F_EXP, PT := T#10S);
    tonLfTrip(IN := (State = ST_RUNNING OR State = ST_TRIPPED) AND PumpRun AND FT101 < 0.5 * P_F_EXP,
              PT := REAL_TO_TIME(P_LOW_FLOW_TRIP_S * 1000.0));
    IF tonLfWarn.Q THEN AlarmWord.AL_LOW_FLOW := TRUE; END_IF
    IF tonLfTrip.Q THEN TripWord.TR_LOW_FLOW := TRUE; END_IF

    tonHtWarn(IN := TT101 > SpEff + 3.0, PT := T#60S);
    tonHtTrip(IN := TT101 > TripLevel, PT := T#5S);
    IF tonHtWarn.Q THEN AlarmWord.AL_HIGH_TEMP := TRUE; END_IF
    IF tonHtTrip.Q THEN TripWord.TR_HIGH_TEMP := TRUE; END_IF

    IF TT101 < Dew + 2.0 THEN AlarmWord.AL_DEW := TRUE; END_IF

    (* inventory: tank water from the gas law vs what the loop temperature predicts *)
    TMean := 0.5 * (TT101 + TT102);
    VtwMeas := P_V_TANK * (1.0 - (P_P_PRE + 1.013) / MAX(PT101 + 1.013, 0.2));
    VtwExp := P_VTW_REF + P_V_SYS * P_BETA * (TMean - P_T_REF);
    InvDeficit := VtwExp - VtwMeas;
    tonInvWarn(IN := InvDeficit > P_INV_WARN_L, PT := T#30S);
    tonInvTrip(IN := InvDeficit > P_INV_TRIP_L AND State <> ST_OFF, PT := T#10S);
    IF tonInvWarn.Q THEN AlarmWord.AL_INVENTORY := TRUE; END_IF
    IF tonInvTrip.Q THEN TripWord.TR_INVENTORY := TRUE; END_IF
    IF PT101 < 0.5 AND State <> ST_OFF THEN TripWord.TR_LOW_STATIC := TRUE; END_IF   (* tank empty *)

    IF PT102 > 3.5 THEN AlarmWord.AL_HIGH_DISCH := TRUE; END_IF
    IF PT102 > 3.8 THEN TripWord.TR_HIGH_DISCH := TRUE; END_IF
    IF PDT101 > 20.0 THEN AlarmWord.AL_FILTER := TRUE; END_IF
    IF LDS301 THEN TripWord.TR_LEAK_TRAY := TRUE; END_IF
    IF LDS302 THEN AlarmWord.AL_LEAK_HOSE := TRUE; END_IF

    FwsBad := XvOpen AND ((FwsDp < 20.0) OR (FT201 < 0.5 AND Valve > 20.0));
    tonFwsWarn(IN := FwsBad, PT := T#10S);
    tonFwsTrip(IN := FwsBad AND State = ST_RUNNING, PT := REAL_TO_TIME(P_FWS_TRIP_S * 1000.0));
    IF tonFwsWarn.Q THEN AlarmWord.AL_FWS_LOST := TRUE; END_IF
    IF tonFwsTrip.Q THEN TripWord.TR_FWS_LOST := TRUE; END_IF

    IF SensorBad AND (State = ST_RUNNING OR State = ST_STARTING) THEN TripWord.TR_SENSOR := TRUE; END_IF
    IF NOT DI_REMOTE_STOP THEN TripWord.TR_REMOTE_STOP := TRUE; END_IF

    IF TripWord <> 0 AND State <> ST_TRIPPED AND State <> ST_OFF THEN
        State := ST_TRIPPED;  tState := 0.0;  tTrip := 0.0;
    END_IF

    (* ------------------------------------------------------------ state machine *)
    HoldValve := FALSE;
    tonRunOk(IN := State = ST_STARTING AND FT101 >= 0.8 * P_F_EXP AND PT101 >= 0.7 AND TT101 < TripLevel, PT := T#10S);
    IF HMI_STOP AND State <> ST_TRIPPED THEN
        State := ST_OFF;  tState := 0.0;       (* operator stop: no trip, no reset needed *)
    END_IF
    CASE State OF
    ST_OFF:
        PumpRun := FALSE;  XvOpen := FALSE;  Permit := FALSE;
        IF rtStart.Q AND TripWord = 0 THEN
            State := ST_STARTING;  tState := 0.0;  PresetLoops := TRUE;
        END_IF

    ST_STARTING:
        PumpRun := TRUE;  XvOpen := TRUE;  Permit := FALSE;
        IF tonRunOk.Q THEN
            State := ST_RUNNING;  tState := 0.0;
        ELSIF tState > 30.0 THEN
            TripWord.TR_START_FAIL := TRUE;  State := ST_TRIPPED;  tState := 0.0;  tTrip := 0.0;
        END_IF

    ST_RUNNING:
        PumpRun := TRUE;  XvOpen := TRUE;  Permit := TRUE;

    ST_TRIPPED:
        Permit := FALSE;
        (* most restrictive action of all active trips *)
        StopAfter := 1.0E9;  CloseXv := FALSE;
        IF TripWord.TR_LOW_STATIC OR TripWord.TR_HIGH_DISCH OR TripWord.TR_START_FAIL OR TripWord.TR_REMOTE_STOP THEN
            StopAfter := 0.0;
        END_IF
        IF TripWord.TR_LOW_FLOW THEN StopAfter := MIN(StopAfter, 30.0); END_IF
        IF TripWord.TR_LEAK_TRAY THEN StopAfter := MIN(StopAfter, 60.0); CloseXv := TRUE; HoldValve := TRUE; END_IF
        IF TripWord.TR_INVENTORY THEN StopAfter := MIN(StopAfter, 60.0); END_IF
        IF TripWord.TR_SENSOR THEN HoldValve := TRUE; END_IF
        PumpRun := tTrip < StopAfter;
        IF CloseXv THEN XvOpen := FALSE; END_IF
        IF rtReset.Q THEN
            TripWord := 0;
            State := ST_OFF;  tState := 0.0;      (* operator restarts with START *)
        END_IF
    END_CASE

    (* ------------------------------------------------------------ pump speed *)
    IF PumpRun THEN
        IF State = ST_STARTING AND tState < 5.0 THEN
            U := 50.0;
            piDp(Preset := TRUE, PresetValue := 50.0, Bias := 0.0, Kp := P_DP_KP, Ti := P_DP_TI, OutMin := P_SPEED_MIN, OutMax := P_SPEED_MAX, Error := 0.0, Applied := 50.0);
            piFlow(Preset := TRUE, PresetValue := 50.0, Bias := 0.0, Kp := P_FL_KP, Ti := P_FL_TI, OutMin := P_SPEED_MIN, OutMax := P_SPEED_MAX, Error := 0.0, Applied := 50.0);
        ELSIF State = ST_TRIPPED AND TripWord.TR_LOW_FLOW THEN
            U := P_SPEED_MAX;                       (* keep trying *)
        ELSIF State = ST_TRIPPED AND TripWord.TR_SENSOR THEN
            U := Speed;                             (* hold *)
        ELSE
            (* dP control with minimum-flow override, max-selected; both loops track the applied output *)
            (* Applied := Speed is last scan's output: one-scan (0.1 s) lag versus the reference, negligible *)
            piDp(Preset := FALSE, Error := P_DP_SP - DpMeas, Bias := 0.0, Kp := P_DP_KP, Ti := P_DP_TI,
                 OutMin := P_SPEED_MIN, OutMax := P_SPEED_MAX, Dt := DT, Conditional := FALSE, Applied := Speed);
            piFlow(Preset := FALSE, Error := P_F_MIN - FT101, Bias := 0.0, Kp := P_FL_KP, Ti := P_FL_TI,
                   OutMin := P_SPEED_MIN, OutMax := P_SPEED_MAX, Dt := DT, Conditional := FALSE, Applied := Speed);
            U := MAX(piDp.Out, piFlow.Out);
        END_IF
        Speed := LIMIT(P_SPEED_MIN, U, P_SPEED_MAX);
    ELSE
        Speed := 0.0;
    END_IF

    (* ------------------------------------------------------------ valve: supply temperature *)
    IF NOT XvOpen OR State = ST_OFF OR HoldValve THEN
        ;   (* valve held in place *)
    ELSIF State = ST_STARTING AND tState < 5.0 THEN
        Valve := P_VALVE_START;
        piValve(Preset := TRUE, PresetValue := 0.0, Bias := 0.0, Error := 0.0, Kp := P_T_KP, Ti := P_T_TI,
                OutMin := P_VALVE_MIN_RUN, OutMax := 100.0);
        Ff := 0.0;
    ELSE
        (* feed-forward: valve position needed at setpoint for the measured duty *)
        FfRaw := 0.0;
        IF P_FF_ENABLE THEN
            Q := 1027.8 * 3890.0 * MAX(FT101, 0.0) / 60000.0 * (TT102 - TT101);     (* W *)
            IF Q > 200.0 THEN
                DtFws := SpEff + (TT102 - TT101) - 1.5 - TT201;
                IF DtFws <= 1.0 THEN
                    FfRaw := 100.0;
                ELSE
                    FReq := Q / (995.7 * 4180.0 * DtFws) * 60000.0;
                    IF FwsDp > 10.0 THEN FfRaw := F_ValvePosForFlow(FReq, FwsDp);
                    ELSE FfRaw := F_ValvePosForFlow(FReq, 50.0); END_IF
                END_IF
            END_IF
            Ff := Ff + DT / P_FF_TF * (FfRaw - Ff);
        ELSE
            Ff := 0.0;
        END_IF
        E := TT101 - SpEff;
        IF ABS(E) < P_T_EDB THEN E := 0.0;
        ELSIF E > 0.0 THEN E := E - P_T_EDB;
        ELSE E := E + P_T_EDB; END_IF
        piValve(Preset := FALSE, Error := E, Bias := Ff, Kp := P_T_KP, Ti := P_T_TI,
                OutMin := P_VALVE_MIN_RUN, OutMax := 100.0, Dt := DT, Conditional := TRUE,
                IBand := P_T_IBAND, Feedback := ZT201, UseFeedback := TRUE, LagBand := 5.0);
        U := piValve.Out;
        IF ABS(U - Valve) > P_VALVE_DB OR U = P_VALVE_MIN_RUN OR U = 100.0 THEN
            Valve := U;
        END_IF
    END_IF

    (* ------------------------------------------------------------ outputs *)
    DO_PUMP_RUN := PumpRun AND NOT DI_DRIVE_FAULT;
    AO_PUMP_SPEED := Speed;
    AO_TCV201 := Valve;
    DO_XV201_OPEN := XvOpen;
    DO_LOAD_PERMIT := Permit;        (* relay coil also in series with the hardware watchdog contact *)
    DO_HORN := (TripWord <> 0) OR (AlarmWord <> 0);
END_PROGRAM

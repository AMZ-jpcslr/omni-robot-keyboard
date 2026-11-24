#ifndef OMNI_ASSUMED_BOARD_H
#define OMNI_ASSUMED_BOARD_H

/* Unmeasured direct connections to IN1 / IN2. INC and STBY are assumed high.
 * P3.0 and P3.1 are the serial port and must remain available. */
#define M1_IN1 P1_0
#define M1_IN2 P1_1
#define M2_IN1 P3_2
#define M2_IN2 P3_3
#define M3_IN1 P3_4
#define M3_IN2 P3_5
#define M4_IN1 P3_6
#define M4_IN2 P3_7

/* Two bits per bridge: 01 = IN1 high, 10 = IN2 high, 00 = coast. */
#define IN1_HIGH 1u
#define IN2_HIGH 2u
#define COAST    0u
#define WHEELS(m1, m2, m3, m4) ((m1) | ((m2) << 2) | ((m3) << 4) | ((m4) << 6))
/* Board channel order is electrical. These two patterns are the final
 * physically verified forward/right outputs from protocol version 1. */
#define FORWARD_INPUTS WHEELS(IN2_HIGH, COAST,    IN1_HIGH, COAST)
#define RIGHT_INPUTS   WHEELS(COAST,    IN1_HIGH, COAST,    IN2_HIGH)
#define TURN_RIGHT_INPUTS WHEELS(IN1_HIGH, IN1_HIGH, IN1_HIGH, IN1_HIGH)
#define PWM_PERIOD_TICKS 20  /* each tick approximately 0.5 ms */
#define PWM_ON_TICKS 14
#if PWM_ON_TICKS < 1 || PWM_ON_TICKS >= PWM_PERIOD_TICKS
#error PWM_ON_TICKS must be less than the period and greater than zero
#endif
#endif

#include <8052.h>
#include "receiver.h"
#include "assumed_board.h"

static unsigned char requested_inputs;
static unsigned char full_duty_inputs;
static unsigned char pwm_phase;

static void output(unsigned char inputs)
{
    M1_IN1 = (inputs & 0x01) != 0;
    M1_IN2 = (inputs & 0x02) != 0;
    M2_IN1 = (inputs & 0x04) != 0;
    M2_IN2 = (inputs & 0x08) != 0;
    M3_IN1 = (inputs & 0x10) != 0;
    M3_IN2 = (inputs & 0x20) != 0;
    M4_IN1 = (inputs & 0x40) != 0;
    M4_IN2 = (inputs & 0x80) != 0;
}

static unsigned char reversed(unsigned char inputs)
{
    return ((inputs & 0x55u) << 1) | ((inputs & 0xaau) >> 1);
}

void motors_init_stopped(void)
{
    output(0);
    requested_inputs = 0;
    full_duty_inputs = 0;
    pwm_phase = 0;
}

static unsigned char direction_inputs(unsigned char direction)
{
    switch (direction) {
        case FORWARD:     return FORWARD_INPUTS;
        case BACKWARD:    return reversed(FORWARD_INPUTS);
        case RIGHT:       return RIGHT_INPUTS;
        case LEFT:        return reversed(RIGHT_INPUTS);
        case FRONT_LEFT:  return FORWARD_INPUTS | reversed(RIGHT_INPUTS);
        case FRONT_RIGHT: return FORWARD_INPUTS | RIGHT_INPUTS;
        case REAR_LEFT:   return reversed(FORWARD_INPUTS | RIGHT_INPUTS);
        case REAR_RIGHT:  return reversed(FORWARD_INPUTS) | RIGHT_INPUTS;
        case TURN_LEFT:   return reversed(TURN_RIGHT_INPUTS);
        case TURN_RIGHT:  return TURN_RIGHT_INPUTS;
        default:          return 0;
    }
}

void motors_set(unsigned char command)
{
    unsigned char base, turn, move;
    output(0);
    pwm_phase = PWM_PERIOD_TICKS - 4;
    if (command < MOVE_TURN_LEFT_BASE) {
        requested_inputs = full_duty_inputs = direction_inputs(command);
        return;
    }
    base = command < MOVE_TURN_RIGHT_BASE ? MOVE_TURN_LEFT_BASE : MOVE_TURN_RIGHT_BASE;
    turn = direction_inputs(base == MOVE_TURN_LEFT_BASE ? TURN_LEFT : TURN_RIGHT);
    move = direction_inputs(FORWARD + command - base);
    /* Each wheel has a turn contribution. Opposite move cancels it; equal
     * move doubles it. Normalize the signed sum to 0, half or full duty. */
    requested_inputs = turn & ~reversed(move);
    full_duty_inputs = turn & move;
}

void motors_tick_half_ms(void)
{
    if (!requested_inputs) return;
    if (++pwm_phase >= PWM_PERIOD_TICKS) {
        pwm_phase = 0;
        output(requested_inputs);
    } else if (pwm_phase == PWM_ON_TICKS / 2) {
        output(full_duty_inputs);
    } else if (pwm_phase == PWM_ON_TICKS) {
        output(0);
    }
}

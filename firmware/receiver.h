#ifndef OMNI_RECEIVER_H
#define OMNI_RECEIVER_H

enum direction {
    STOP, FORWARD, BACKWARD, LEFT, RIGHT, FRONT_LEFT, FRONT_RIGHT,
    REAR_LEFT, REAR_RIGHT, TURN_LEFT, TURN_RIGHT,
    MOVE_TURN_LEFT_BASE, MOVE_TURN_RIGHT_BASE = MOVE_TURN_LEFT_BASE + 8,
    LAST_COMMAND = MOVE_TURN_RIGHT_BASE + 7
};

void motors_init_stopped(void);
void motors_set(unsigned char direction);
void motors_tick_half_ms(void);

void receiver_byte(unsigned char byte);
void receiver_tick_10ms(void);
unsigned char receiver_waiting(void);
void receiver_check_obstacles(void);
unsigned char receiver_output(void);

#endif

#include "receiver.h"
#ifdef OBSTACLE_GUARD
#include "obstacle_guard.h"
static unsigned char requested;
#endif

static unsigned char remaining_ticks;
static unsigned char phase;
static unsigned char command;
static unsigned char direction;

static void change_direction(unsigned char next)
{
#ifdef OBSTACLE_GUARD
    requested = next;
    next = obstacle_filter(next);
#endif
    if (direction != next) {
        motors_set(next);
        direction = next;
    }
}

#ifdef OBSTACLE_GUARD
void receiver_check_obstacles(void)
{
    obstacle_sample();
    change_direction(requested);
}

unsigned char receiver_output(void)
{
    return direction;
}
#endif

unsigned char receiver_waiting(void)
{
    return remaining_ticks == 0;
}

void receiver_tick_10ms(void)
{
    if (remaining_ticks && --remaining_ticks == 0) {
        change_direction(STOP);
        phase = 0;
    }
}

void receiver_byte(unsigned char byte)
{
    /* Frame: A5, direction, one's complement of direction. */
    if (byte == 0xA5) {
        phase = 1;
    } else if (phase == 1 && byte <= LAST_COMMAND) {
        command = byte;
        phase = 2;
    } else if (phase == 2 && (unsigned char)(command ^ byte) == 0xFF) {
        phase = 0;
        if (command == STOP || remaining_ticks) {
            remaining_ticks = 25;
            change_direction(command);
        }
    } else {
        phase = 0;
        remaining_ticks = 0;
        change_direction(STOP);
    }
}

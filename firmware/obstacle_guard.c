#include "receiver.h"
#include "obstacle_guard.h"
#include "sensor_adc.h"
#include "sensor_config.h"

/* Bit order by physical label: front-left, rear-right, rear-left, front-right. */
static const __code unsigned char approach[] = {0, 9, 6, 5, 10, 1, 8, 4, 2};
static unsigned char occupied = 15, valid, index, held_move;
static unsigned char clear_count[4];

void obstacle_init(void)
{
    sensor_adc_init();
}

unsigned char obstacle_mask(void)
{
    return valid == 15 ? occupied : 15;
}

void obstacle_sample(void)
{
    unsigned char bitmask = 1u << index;
    unsigned int value = sensor_read(channel[index]);
    if (value == 0xffff) {
        valid &= ~bitmask;
        occupied |= bitmask;
        clear_count[index] = 0;
    } else {
        valid |= bitmask;
        if (rising[index] ? value >= trip[index] : value <= trip[index]) {
            occupied |= bitmask;
            clear_count[index] = 0;
        } else if (rising[index] ? value <= release[index] : value >= release[index]) {
            if (clear_count[index] < 8) ++clear_count[index];
            if (clear_count[index] == 8) occupied &= ~bitmask;
        } else {
            clear_count[index] = 0;
        }
    }
    index = (index + 1) & 3;
}

unsigned char obstacle_filter(unsigned char command)
{
    unsigned char move = command;
    if (command >= MOVE_TURN_RIGHT_BASE) move = FORWARD + command - MOVE_TURN_RIGHT_BASE;
    else if (command >= MOVE_TURN_LEFT_BASE) move = FORWARD + command - MOVE_TURN_LEFT_BASE;
    if (move != held_move) held_move = STOP;
    if (valid != 15) return STOP;
    if (move >= FORWARD && move <= REAR_RIGHT) {
        if (approach[move] & occupied) held_move = move;
        if (held_move == move) return STOP;
    }
    return command;
}

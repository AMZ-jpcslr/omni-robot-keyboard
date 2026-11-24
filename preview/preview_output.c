#include "../firmware/receiver.h"

static unsigned char output;

void motors_set(unsigned char direction)
{
    output = direction;
}

unsigned char preview_direction(void)
{
    return output;
}

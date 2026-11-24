#ifndef OMNI_OBSTACLE_GUARD_H
#define OMNI_OBSTACLE_GUARD_H
void obstacle_init(void);
void obstacle_sample(void);
unsigned char obstacle_filter(unsigned char command);
unsigned char obstacle_mask(void);
#endif

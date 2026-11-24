#ifndef SENSOR_ADC_H
#define SENSOR_ADC_H

/* ADuC814, ADCCON1/2 and ADC result registers. DACs stay powered down. */
__sfr __at (0xEF) ADCCON1;
__sfr __at (0xD8) ADCCON2;
__sfr __at (0xD9) ADCDATAL;
__sfr __at (0xDA) ADCDATAH;

static unsigned int sensor_read(unsigned char channel)
{
    unsigned char limit = 64;
    unsigned char high;
    ADCCON2 = channel | 0x10;
    while (!(ADCCON2 & 0x80) && --limit) { }
    high = ADCDATAH;
    if (!limit || (high >> 4) != channel) return 0xffff;
    return ((unsigned int)(high & 15) << 8) | ADCDATAL;
}

static void sensor_adc_init(void)
{
    /* Reset leaves P1.2..7 latches high (analog inputs). */
    ADCCON1 = 0xBC; /* on-chip reference, /32 clock, 4 acquisition clocks */
}
#endif

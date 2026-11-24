#include <8052.h>
#include "receiver.h"
#include "sensor_adc.h"

__sfr __at (0xD7) PLLCON;
static const __code char hex[] = "0123456789ABCDEF";

static void send_char(char c)
{
    while (!TI) { }
    TI = 0;
    SBUF = c;
}

/* Diagnostic image: no receive handler or motor drive command. */
void main(void)
{
    unsigned char ch;
    unsigned int sample;
    EA = 0;
    motors_init_stopped();
    PLLCON = 0;
    T2CON = 0;
    RCAP2H = TH2 = 0xff;
    RCAP2L = TL2 = 0xc9;
    SCON = 0x40;
    T2CON = 0x34;
    TI = 1;
    sensor_adc_init();
    for (;;) {
        send_char('@');
        for (ch = 0; ch < 6; ++ch) {
            sample = sensor_read(ch);
            send_char(hex[sample >> 12]);
            send_char(hex[(sample >> 8) & 15]);
            send_char(hex[(sample >> 4) & 15]);
            send_char(hex[sample & 15]);
        }
        send_char('\n');
    }
}

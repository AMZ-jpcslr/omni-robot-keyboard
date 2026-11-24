/* SDCC, ADuC814 with its 32.768 kHz crystal. See assumed_board.h for wiring. */
#include <8052.h>
#include "receiver.h"

__sfr __at (0xD7) PLLCON;
#ifdef OBSTACLE_GUARD
#include "obstacle_guard.h"
static const __code char banner[] = "OMNI814/4\n";
static const __code char hex[] = "0123456789ABCDEF";
#else
static const __code char banner[] = "OMNI814/3\n";
#endif

void main(void)
{
    unsigned char announce_ticks = 0;
    unsigned char tx_index = sizeof(banner) - 1;
    unsigned char half_ms_count = 0;
#ifdef OBSTACLE_GUARD
    unsigned char report_ticks = 0, report_index = 5;
    unsigned char report[5];
#endif

    EA = 0;
    motors_init_stopped();
    PLLCON = 0;                  /* Core 16.777216 MHz. */
#ifdef OBSTACLE_GUARD
    obstacle_init();
#endif
    T2CON = 0;
    RCAP2H = TH2 = 0xFF;
    RCAP2L = TL2 = 0xC9;        /* UART ~9533 baud, nominal host 9600. */
    SCON = 0x50;                /* 8-bit UART, receiver enabled. */
    T2CON = 0x34;               /* RCLK, TCLK, TR2. */
    TI = 1;
    TMOD = 0x01;
    TR0 = 0;
    TF0 = 0;
    TH0 = 0xFD;
    TL0 = 0x45;                 /* 699 machine cycles, about 0.5 ms. */
    TR0 = 1;

    for (;;) {
        if (TF0) {
            TR0 = 0;
            TH0 = 0xFD;
            TL0 = 0x45;
            TF0 = 0;
            TR0 = 1;
            if (++half_ms_count == 20) {
                half_ms_count = 0;
                receiver_tick_10ms();
                if (announce_ticks) --announce_ticks;
#ifdef OBSTACLE_GUARD
                if (report_ticks) --report_ticks;
#endif
            }
#ifdef OBSTACLE_GUARD
            receiver_check_obstacles();
#endif
            motors_tick_half_ms();
        }
        if (RI) {
            unsigned char byte = SBUF;
            RI = 0;
            receiver_byte(byte);
        }
        if (!announce_ticks && receiver_waiting()
#ifdef OBSTACLE_GUARD
                && report_index == 5
#endif
        ) {
            tx_index = 0;
            announce_ticks = 40;
        }
        if (TI && tx_index < sizeof(banner) - 1) {
            TI = 0;
            SBUF = banner[tx_index++];
        }
#ifdef OBSTACLE_GUARD
        else if (tx_index == sizeof(banner) - 1) {
            if (!report_ticks && report_index == 5) {
                unsigned char out = receiver_output();
                report[0] = '!';
                report[1] = hex[obstacle_mask()];
                report[2] = hex[out >> 4];
                report[3] = hex[out & 15];
                report[4] = '\n';
                report_index = 0;
                report_ticks = 8;
            }
            if (TI && report_index < 5) {
                TI = 0;
                SBUF = report[report_index++];
            }
        }
#endif
    }
}

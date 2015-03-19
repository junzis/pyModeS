import decoder
import re

with open('data.txt', 'r') as f:
    lines = f.readlines()

for line in lines:
    m = re.search('^(\d+\-\d+\-\d+T\d+\:\d+\:\d+\.\d+)\s*(\S*).*$', line)

    time = m.group(1)
    msg = m.group(2)

    df = decoder.get_df(msg)
    tc = decoder.get_tc(msg)
    ca = decoder.get_ca(msg)

    if df==17:
        addr = decoder.get_icao_addr(msg)

        if tc>=1 and tc<=4:
            # aircraft identification
            callsign = decoder.get_callsign(msg)
            print msg, '->', 'ID:', callsign

        elif tc>=9 and tc<=18:
            # airbone postion frame
            alt = decoder.get_alt(msg)
            oe = decoder.get_oe_flag(msg)  # odd or even frame
            # cprlat = decoder.get_cprlat(msg)
            # cprlon = decoder.get_cprlon(msg)
            print msg, '->',  'CPR odd frame' if oe else 'CPR even frame'

        elif tc==19:
            # airbone velocity frame
            sh = decoder.get_speed_heading(msg)
            print msg, '->', 'Speed:', sh[0], 'Heading:', sh[1]
    else:
        print df
        pass
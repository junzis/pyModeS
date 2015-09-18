import decoder

print 'Testing the ADS-B decoder'
print '---------------------------'
print

# decode call sign test
msg = '8D51004E20092578DB782072C825'
cs = decoder.get_callsign(msg)
print 'Message:', msg
print 'Call sign:', cs
print

# decode position
msg0 = '8D51004E901DF3041D06127582A1'
msg1 = '8D51004E901DF66EB4FEE010C7A9'
t0 = 1442566675
t1 = 1442566674
pos = decoder.get_position(msg0, msg1, t0, t1)
print 'Message E:', msg0
print 'Message O:', msg1
print 'Position:', pos
print

# decode velocity
msg = '8D51004E99850702685C00E582E4'
sh = decoder.get_speed_heading(msg)
print 'Message:', msg
print 'Speed and heading:', sh
print

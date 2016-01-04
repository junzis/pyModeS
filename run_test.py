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
msg0 = '8D40058B58C901375147EFD09357'
msg1 = '8D40058B58C904A87F402D3B8C59'
t0 = 1446332400
t1 = 1446332405
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

# test NIC
# decode position
msg = '8D40058B58C901375147EFD09357'
nic = decoder.get_nic(msg1)
print 'Message:', msg
print 'NIC:', nic
print

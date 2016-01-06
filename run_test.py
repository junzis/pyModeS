import decoder

print '*************************'
print 'Testing the ADS-B decoder'
print '*************************'
print

# decode call sign test
print "------- Test Callsign -------"
msg_cs = '8D51004E20092578DB782072C825'
cs = decoder.get_callsign(msg_cs)
print 'Message:', msg_cs
print 'Call sign:', cs
print

# decode position
print "------- Test Postiions -------"
msg_pos_0 = '8D40058B58C901375147EFD09357'
msg_pos_1 = '8D40058B58C904A87F402D3B8C59'
t0 = 1446332400
t1 = 1446332405
pos = decoder.get_position(msg_pos_0, msg_pos_1, t0, t1)
print 'Message E:', msg_pos_0
print 'Message O:', msg_pos_1
print 'Position:', pos
print

# decode velocity
print "------- Test Velocity -------"
msg_v_s1 = '8D485020994409940838175B284F'   # subtype 1
msg_v_s3 = '8DA05F219B06B6AF189400CBC33F'   # subtype 3
v1 = decoder.get_velocity(msg_v_s1)
v2 = decoder.get_velocity(msg_v_s3)
print 'Message:', msg_v_s1
print 'velocity:', v1
print 'Message:', msg_v_s3
print 'velocity:', v2
print

# test NIC
print "------- Test NIC -------"
msg_nic = '8D40621D58C382D690C8AC2863A7'
nic = decoder.get_nic(msg_nic)
print 'Message:', msg_nic
print 'NIC:', nic
print

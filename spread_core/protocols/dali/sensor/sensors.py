# from dali import address
# from dali.device import general, light_sensor_ext
#
#
# class Sensor(Device):
#     def __init__(self, addr, bus=None):
#         super().__init__(addr, bus=bus)
#         self.update()
#
#     @property
#     def instance(self):
#         raise
#
#     def update(self):
#         i = self.bus.get_interface()
#
#         r = i.send(general.QueryEventScheme(self.address_obj, self.instance))
#         self.update_value('EventScheme', r.value.as_integer)
#
#         r = i.send(general.QueryEventPriority(self.address_obj, self.instance))
#         self.update_value('EventPriority', r.value.as_integer)
#
#         r = [
#             i.send(
#                 general.QueryEventFilterL(self.address_obj, self.instance)
#             ).value.as_integer,
#             i.send(
#                 general.QueryEventFilterM(self.address_obj, self.instance)
#             ).value.as_integer,
#             i.send(
#                 general.QueryEventFilterH(self.address_obj, self.instance)
#             ).value.as_integer
#         ]
#
#         self.update_value('EventFilter', r)
#
#     @staticmethod
#     def of(addr, bus, d_type):
#         if type == LightSensor.type_id():
#             return LightSensor(addr, bus)
#         elif type == PresenceSensor.type_id():
#             return PresenceSensor(addr, bus)
#
#
# class LightSensor(Sensor):
#     def __init__(self, addr, bus):
#         super().__init__(addr, bus)
#
#     def update(self):
#         super().update()
#
#         i = self.bus.get_interface()
#
#         r = i.send(light_sensor_ext.QueryDeadTimeTimer(self.address_obj, self.instance))
#         self.update_value('DeadTime', r.value.as_integer)
#
#         r = i.send(light_sensor_ext.QueryReportTimer(self.address_obj, self.instance))
#         self.update_value('ReportTime', r.value.as_integer)
#
#         r = i.send(light_sensor_ext.QueryHysteresis(self.address_obj, self.instance))
#         self.update_value('Hysteresis', r.value.as_integer)
#
#         r = i.send(light_sensor_ext.QueryHysteresisMin(self.address_obj, self.instance))
#         self.update_value('HysteresisMin', r.value.as_integer)
#
#     @property
#     def instance(self):
#         return address.InstanceType(3)
#
#     @staticmethod
#     def type_id():
#         return 3
#
#
# class PresenceSensor(Sensor):
#     def __init__(self, addr, bus):
#         super().__init__(addr, bus)
#
#     @property
#     def instance(self):
#         return address.InstanceType(4)
#
#     @staticmethod
#     def type_id():
#         return 4

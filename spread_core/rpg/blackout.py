
class Blackout:

    # shuxer1 = [0, 0, 10, 10, 0, 0, 0, 0, 0]
    # shuxer2 = [0, 0, 50, 50, 0, 0, 0, 0, 0]
    shuxer1 = {
        # dimming light
        '635561': 0,
        '635562': 10,
        '635563': 10,
        '635564': 0,
        '659939': 0,
        #  swiching light
        '659853': 0,
        '659854': 0,
        '659855': 0,
        '659856': 0,
    }
    shuxer2 = {
        # dimming light
        '635561': 0,
        '635562': 0,
        '635563': 50,
        '635564': 50,
        '659939': 0,
        #  swiching light
        '659853': 0,
        '659854': 0,
        '659855': 0,
        '659856': 0,
    }

    saved_light = {
        # dimming light
        '635561': 0,
        '635562': 0,
        '635563': 0,
        '635564': 0,
        '659939': 0,
        #  swiching light
        '659853': 0,
        '659854': 0,
        '659855': 0,
        '659856': 0,
    }
    def __init__(self, diMask, diList, daliList):

        self._is_shuxer = False
        self._reg = 0
        self._mask = diMask
        self.diList = diList
        self.daliList = daliList


    def checkout(self):
        reg = 0
        for device in self.diList:
            if device.type == 'blackout_sw1' and device.state == True:
                reg = 1
            elif  device.type == 'blackout_sw2' and device.state == True:
                reg = 2

        return reg

    def work(self):

        if None not in  [t[1] for t in list(self._mask.values())]:
            self._reg = self.checkout()
            if False in [t[1] for t in list(self._mask.values()) if t[0]=='door_sw']:
                if self._reg != 0:
                    if self._is_shuxer != True:
                        self.shuxer()
                        return
                    else:
                        return
                else:
                    if self._is_shuxer == True:
                        self.entwarnung()
                        return
                    else:
                        return

            else:
                if self._is_shuxer == True:
                    self.entwarnung()
                    return
                else:
                    return

    def shuxer(self):
        self.save_light()
        if self._reg == 1:
            ii = 0
            self._is_shuxer = True

            for dev in self.daliList:
                if dev.state is not None:
                    level=self.shuxer1['{}'.format(str(dev.dev['id']))]
                    dev.setLevel(level)
                    if dev.dev['type'] == 'DimmingLight':
                        dev.dumpMqtt(data=level)
                    elif dev.dev['type'] == 'SwitchingLight':
                        dev.dumpMqtt(data=level, fl=1)


        elif self._reg == 2:
            ii = 0
            self._is_shuxer = True
            for dev in self.daliList:
                if dev.state is not None:
                    level = self.shuxer2['{}'.format(dev.dev['id'])]
                    dev.setLevel(level)
                    if dev.dev['type'] == 'DimmingLight':
                        dev.dumpMqtt(data=level)
                    elif dev.dev['type'] == 'SwitchingLight':
                        dev.dumpMqtt(data=level, fl=1)




    def save_light(self):
        for dev in self.daliList:
            if dev.state is not None:
                self.saved_light[str(dev.dev['id'])] = dev.lastLevel
            elif dev.state is None:
                self.saved_light[str(dev.dev['id'])] = dev.lastLevel
    # TODO: добавить None значения в стоварь SAVED_DATA и проверку их присутствия после запоминания состояния света

    def entwarnung(self):

        for dev in self.daliList:
            if dev.state is not None:
                level=self.saved_light['{}'.format(dev.dev['id'])]
                dev.setLevel(level)
                if dev.dev['type']=='DimmingLight':
                    dev.dumpMqtt(data=level)
                elif dev.dev['type']=='SwitchingLight':
                    dev.dumpMqtt(data=level, fl=1)

        self._is_shuxer = False


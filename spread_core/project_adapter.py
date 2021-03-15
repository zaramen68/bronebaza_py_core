import json
import os
import shutil
import sys
import zipfile
import zlib
from time import sleep

from spread_core import mqtt
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging


class ProjectAdapterLauncher(Launcher):
    # ZIP_TOPIC = 'data_project_ctp'
    ZIP_TOPIC = 'Project/2434/Ctp'
    ZIP_NAME = os.path.basename(config['CTP_PATH'])
    HASH_NAME = ZIP_NAME + '.hash'
    cd = os.path.dirname(config['CTP_PATH']) + '/'
    zip_data = None
    project_id = None
    _dumped = False
    _publish_count = 0

    def __init__(self):
        self._manager = self
        super(ProjectAdapterLauncher, self).__init__()

    def start(self):
        # while True:
        if 'CTP_PATH' not in config:
            raise BaseException('"CTP_PATH" is not set!')
        if os.path.exists(self.cd + self.HASH_NAME):
            os.remove(self.cd + self.HASH_NAME)

        try:
            hash_data = dict()
            if os.path.exists(self.cd + self.HASH_NAME):
                with open(self.cd + self.HASH_NAME, 'rb') as hash_file:
                    hash_data = json.loads(hash_file.read().decode())
        except BaseException as ex:
            print(str(ex))
        try:
            with open(self.cd + self.ZIP_NAME, 'rb') as zip_file:
                zip_data = zip_file.read()
        except BaseException as ex:
            logging.exception(ex)
        else:
            zip_hash = zlib.crc32(zip_data)
            on_remove = hash_data.copy()
            if self.ZIP_NAME not in hash_data or hash_data[self.ZIP_NAME] != zip_hash:
                project_id, project_data = self.read_project(self.cd)
                hash_data[self.ZIP_NAME] = zip_hash
                for file in project_data:
                    file_hash = project_data[file]['hash']
                    if file not in hash_data or file_hash != hash_data[file]:
                        topic = mqtt.TopicProject(project_id, file)
                        self.publish(str(topic), project_data[file]['data'], retain=True)
                    hash_data[file] = file_hash
                    if file in on_remove:
                        on_remove.pop(file)

                for file in on_remove:
                    if file == self.ZIP_NAME:
                        continue
                    topic = mqtt.TopicProject(project_id, file)
                    self.publish(str(topic), b'', True)
                    if file in hash_data:
                        hash_data.pop(file)

                with open(self.cd + self.HASH_NAME, 'wb') as hash_file:
                    hash_file.write(json.dumps(hash_data).encode('utf-8'))
                self.publish(self.ZIP_TOPIC, data=b'', retain=True)
                self.publish(self.ZIP_TOPIC, data=zip_data, retain=True)
                logging.info('CTP packet of {} size emitted'.format(len(zip_data)))
                self.subscribe(self.ZIP_TOPIC)
            else:
                logging.info('project not changed. sleep 5 sec')
        finally:
            logging.info('{} packets sent'.format(self._publish_count))
            sleep(5)

    def read_project(self, cd):
        project_data = dict()
        pid = -1
        try:
            shutil.rmtree(cd + 'data/', ignore_errors=True)
        except BaseException as ex:
            logging.exception(ex)

        zip_ref = zipfile.ZipFile(cd + self.ZIP_NAME, 'r')
        zip_ref.extractall(cd + 'data')
        zip_ref.close()

        files = os.listdir(cd + 'data')

        for file in files:
            with open(cd + 'data/' + file, 'rb') as file_data:
                file_data = file_data.read()
                file_data = dict(hash=zlib.crc32(file_data), data=file_data)
                if file == 'header.json':
                    data = json.loads(file_data['data'].decode())
                    if 'header' in data and 'project' in data['header'] and 'id' in data['header']['project']:
                        pid = data['header']['project']['id']
            project_data[file] = file_data
        return pid, project_data

    def publish(self, topic, data, retain=True):
        str_data = '<<large_data>>'
        if len(data) < 2000:
            str_data = str(data)
        try:
            self.mqttc.publish(topic=topic, payload=data, retain=retain)
        except BaseException as ex:
            logging.exception(ex)
        self._publish_count += 1
        logging.info(str.format('[PUBLISHING] => topic: {}, size:{}, data: {}', topic, len(data), str_data))

    def on_message(self, mosq, obj, msg):
        if msg.topic == self.ZIP_TOPIC:
            logging.info('CTP packet of {} size received'.format(len(msg.payload)))
            self.mqttc.loop_stop(True)
            self.mqttc.disconnect()
            sys.exit(0)


def run():
    ProjectAdapterLauncher()


if __name__ == '__main__':
    run()

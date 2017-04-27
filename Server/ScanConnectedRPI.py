from InterfaceSerRPIs import InterfaceSerRPIs
import time

class ScannerRPI:
    def __init__(self):
        self.list_rpi_connected = []
        self.list_rpi_not_connected = []

    def add_slave_RPI(self, ip):
        self.list_rpi_connected.append(ip)
        if ip in self.list_rpi_not_connected:
            self.list_rpi_not_connected.pop(ip)
        # ~ check s'il n'a pas planter et le relancer si possible

    def delete_slave_RPI(self, ip):
        self.list_rpi_connected.pop(ip)
        self.list_rpi_not_connected.append(ip)


    def regular_scan(self):
        '''
        Envoi d'un ping version socket pour mettre a jour les RPI connectées peut être utile
        Pour chercher les raisons de non-activité et du dépannage à automatisé si possible
        :return:
        '''
        while True:
            if len(self.list_rpi_connected) > 0:
                self.scan_rpi_connected()
            time.sleep(60)

    def scan_rpi_connected(self):

        for ip in self.list_rpi_connected:
            print(ip)
            print('I try ?')
            try:
                InterfaceSerRPIs.(ip).presence()
                print(ip + ' is available')
            except:
                print(ip + ' is not available')


rpi = ScannerRPI()
rpi.add_slave_RPI("127.0.0.1")
rpi.regular_scan()
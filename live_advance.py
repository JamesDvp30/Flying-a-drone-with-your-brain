import socket
import cortex
from cortex import Cortex
import queue
import time
import threading
from collections import deque


class LiveAdvance():
    """
    A class to show mental command data at live mode of trained profile.
    You can load a profile trained on EmotivBCI or via train.py example

    Attributes
    ----------
    c : Cortex
        Cortex communicate with Emotiv Cortex Service

    Methods
    -------
    start():
        To start a live mental command  process from starting a websocket
    load_profile(profile_name):
        To load an existed profile or create new profile for training
    unload_profile(profile_name):
        To unload an existed profile or create new profile for training
    get_active_action(profile_name):
        To get active actions for the mental command detection.
    get_sensitivity(profile_name):
        To get the sensitivity of the 4 active mental command actions.
    set_sensitivity(profile_name):
        To set the sensitivity of the 4 active mental command actions.
    """


    def __init__(self, app_client_id, app_client_secret, **kwargs):
        self.c = Cortex(app_client_id, app_client_secret, debug_mode=True, **kwargs)
        self.c.bind(create_session_done=self.on_create_session_done)
        self.c.bind(query_profile_done=self.on_query_profile_done)
        self.c.bind(load_unload_profile_done=self.on_load_unload_profile_done)
        self.c.bind(save_profile_done=self.on_save_profile_done)
        self.c.bind(new_com_data=self.on_new_com_data)
        self.c.bind(get_mc_active_action_done=self.on_get_mc_active_action_done)
        self.c.bind(mc_action_sensitivity_done=self.on_mc_action_sensitivity_done)
        self.c.bind(inform_error=self.on_inform_error)
        self.command_queue = queue.Queue()
        self.socket_sender = None

        self.command_history = deque(maxlen=40)  # Mantener las últimas 40 muestras de comandos
        self.target_words = ["drop", "right", "left", "lift", "neutral"]  # Palabras objetivo para contar
        self.last_print_time = 0  # Registro del último momento en que se imprimió y guardó




    def start(self, profile_name, headsetId=''):
        """
        To start live process as below workflow
        (1) check access right -> authorize -> connect headset->create session
        (2) query profile -> get current profile -> load/create profile
        (3) get MC active action -> get MC sensitivity -> set new MC sensitivity -> save profile
        (4) subscribe 'com' data to show live MC data
        Parameters
        ----------
        profile_name : string, required
            name of profile
        headsetId: string , optional
             id of wanted headet which you want to work with it.
             If the headsetId is empty, the first headset in list will be set as wanted headset
        Returns
        -------
        None
        """
        if profile_name == '':
            raise ValueError('Empty profile_name. The profile_name cannot be empty.')

        self.profile_name = profile_name
        self.c.set_wanted_profile(profile_name)

        if headsetId != '':
            self.c.set_wanted_headset(headsetId)

        self.c.open()

    def load_profile(self, profile_name):
        """
        To load a profile

        Parameters
        ----------
        profile_name : str, required
            profile name

        Returns
        -------
        None
        """
        self.c.setup_profile(profile_name, 'load')

    def unload_profile(self, profile_name):
        """
        To unload a profile
        Parameters
        ----------
        profile_name : str, required
            profile name

        Returns
        -------
        None
        """
        self.c.setup_profile(profile_name, 'unload')

    def save_profile(self, profile_name):
        """
        To save a profile

        Parameters
        ----------
        profile_name : str, required
            profile name

        Returns
        -------
        None
        """
        self.c.setup_profile(profile_name, 'save')

    def subscribe_data(self, streams):
        """
        To subscribe to one or more data streams
        'com': Mental command
        'fac' : Facial expression
        'sys': training event

        Parameters
        ----------
        streams : list, required
            list of streams. For example, ['sys']

        Returns
        -------
        None
        """
        self.c.sub_request(streams)

    def get_active_action(self, profile_name):
        """
        To get active actions for the mental command detection.
        Maximum 4 mental command actions are actived. This doesn't include "neutral"

        Parameters
        ----------
        profile_name : str, required
            profile name

        Returns
        -------
        None
        """
        self.c.get_mental_command_active_action(profile_name)

    def get_sensitivity(self, profile_name):
        """
        To get the sensitivity of the 4 active mental command actions. This doesn't include "neutral"
        It will return arrays of 4 numbers, range 1 - 10
        The order of the values must follow the order of the active actions, as returned by mentalCommandActiveAction
        If the number of active actions < 4, the rest numbers are ignored.

        Parameters
        ----------
        profile_name : str, required
            profile name

        Returns
        -------
        None
        """
        self.c.get_mental_command_action_sensitivity(profile_name)

    def set_sensitivity(self, profile_name, values):
        """
        To set the sensitivity of the 4 active mental command actions. This doesn't include "neutral".
        The order of the values must follow the order of the active actions, as returned by mentalCommandActiveAction
        
        Parameters
        ----------
        profile_name : str, required
            profile name
        values: list, required
            list of sensitivity values. The range is from 1 (lowest sensitivy) - 10 (higest sensitivity)
            For example: [neutral, push, pull, lift, drop] -> sensitivity [7, 8, 3, 6] <=> push : 7 , pull: 8, lift: 3, drop:6
                         [neutral, push, pull] -> sensitivity [7, 8, 5, 5] <=> push : 7 , pull: 8  , others resvered


        Returns
        -------
        None
        """
        self.c.set_mental_command_action_sensitivity(profile_name, values)

    # callbacks functions
    def on_create_session_done(self, *args, **kwargs):
        print('on_create_session_done')
        self.c.query_profile()

    def on_query_profile_done(self, *args, **kwargs):
        print('on_query_profile_done')
        self.profile_lists = kwargs.get('data')
        if self.profile_name in self.profile_lists:
            # the profile is existed
            self.c.get_current_profile()
        else:
            # create profile
            self.c.setup_profile(self.profile_name, 'create')

    def on_load_unload_profile_done(self, *args, **kwargs):
        is_loaded = kwargs.get('isLoaded')
        print("on_load_unload_profile_done: " + str(is_loaded))

        if is_loaded == True:
            # get active action
            self.get_active_action(self.profile_name)
        else:
            print('The profile ' + self.profile_name + ' is unloaded')
            self.profile_name = ''

    def on_save_profile_done(self, *args, **kwargs):
        print('Save profile ' + self.profile_name + " successfully")
        # subscribe mental command data
        stream = ['com']
        self.c.sub_request(stream)

    def envioporsocket(self,comando): #Aqui seremos el cliente, el servidor sera la VM
        host = '192.168.1.124'
        port = 5000
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall(comando)

    def on_new_com_data(self, *args, **kwargs):
        """
        To handle mental command data emitted from Cortex
        Returns
        -------
        data: dictionary
             the format such as {'action': 'neutral', 'power': 0.0, 'time': 1590736942.8479}
        """
        data = kwargs.get('data')
        if data:
            # Agregar el comando actual al historial
            command = data.get('action', '').lower()  # Asegurarse de que la primera letra esté en mayúscula
            self.command_history.append(command)
            # Verificar si ha pasado al menos 8 segueing desde la última impresión
            current_time = time.time()
            if current_time - self.last_print_time >= 8:
                # Contar la cantidad de veces que aparecen las palabras objetivo
                counts = {word: self.command_history.count(word) for word in self.target_words}
                # Verificar si la mayoría de los comandos son alguna de las palabras objetivo
                majority_word = max(counts, key=counts.get)
                majority_count = counts[majority_word]

                if majority_count >= 20:  # Si 20 o más de las últimas 40 muestras son de alguna palabra objetivo
                    self.guardar_datos_en_csv(majority_word, 'C:/Users/James/Desktop/cortex-v2-example-master/datos.txt')
                    print(f"La mayoría de los comandos son: {majority_word}")
                    comando = majority_word
                    comando_encoded = comando.encode('utf-8')
                    self.envioporsocket(comando_encoded)
                    self.last_print_time = current_time  # Actualizar el registro del último momento de impresión




    def on_get_mc_active_action_done(self, *args, **kwargs):
        data = kwargs.get('data')
        print('on_get_mc_active_action_done: {}'.format(data))
        self.get_sensitivity(self.profile_name)

    def on_mc_action_sensitivity_done(self, *args, **kwargs):
        data = kwargs.get('data')
        print('on_mc_action_sensitivity_done: {}'.format(data))
        if isinstance(data, list):
            # get sensivity
            new_values = [5,5,7,7]
            self.set_sensitivity(self.profile_name, new_values)
        else:
            # set sensitivity done -> save profile
            self.save_profile(self.profile_name)

    def on_inform_error(self, *args, **kwargs):
        error_data = kwargs.get('error_data')
        error_code = error_data['code']
        error_message = error_data['message']

        print(error_data)

        if error_code == cortex.ERR_PROFILE_ACCESS_DENIED:
            # disconnect headset for next use
            print('Get error ' + error_message + ". Disconnect headset to fix this issue for next use.")
            self.c.disconnect_headset()

    def guardar_datos_en_csv(self,datos, nombre_archivo):
        # Lista de campos que se utilizarán como encabezados en el archivo CSV
            with open(nombre_archivo, 'a') as archivo:
                datos_str = str(datos) + '\n'
                archivo.write(datos_str)



# Rest of your code remains the same

# -----------------------------------------------------------
# 
# GETTING STARTED
#   - Please reference to https://emotiv.gitbook.io/cortex-api/ first.
#   - Connect your headset with dongle or bluetooth. You can see the headset via Emotiv Launcher
#   - Please make sure the yo   ur_app_client_id and your_app_client_secret are set before starting running.
#   - The function on_create_session_done,  on_query_profile_done, on_load_unload_profile_done will help 
#          handle create and load an profile automatically . So you should not modify them
#   - After the profile is loaded. We test with some advanced BCI api such as: mentalCommandActiveAction, mentalCommandActionSensitivity..
#      But you can subscribe 'com' data to get live mental command data after the profile is loaded
# RESULT
#    you can run live mode with the trained profile. the data as below:
#    {'action': 'push', 'power': 0.85, 'time': 1647525819.0223}
#    {'action': 'pull', 'power': 0.55, 'time': 1647525819.1473}
# 
# -----------------------------------------------------------

def main():

    # Please fill your application clientId and clientSecret before running script
    your_app_client_id = 'RDwU147NFCMZPXIW5L5fzrQotq7phDTwMLoAc6ec'
    your_app_client_secret = 'ckAeNsKjRCcwMeYDRJJaYwrSDnfqUplZtLhfzvUhBM5x2QX9pRwIOSzlBLGKlfSnxofQUC41Qps10v27FWtGVIeCp4I2yOlfo4xAl31I4XkynnhIRgfKJfC7mbypE3da'

    # Init live advance
    l = LiveAdvance(your_app_client_id, your_app_client_secret)

    trained_profile_name = 'Dario2023P2' # Please set a trained profile name here
    l.start(trained_profile_name)


if __name__ =='__main__':
    main()


# -----------------------------------------------------------

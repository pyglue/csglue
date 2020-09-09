import pymem, math, win32api, requests
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

_aimbone = 8 #8 = head
_fov = 120.0

def get_offsets():
    while True:
        try:
            r = requests.get('https://raw.githubusercontent.com/frk1/hazedumper/master/csgo.json')
            return r.json()
        except Exception as e:
            sleep(1)

class Chams():
    def __init__(self, pm, modules, offsets):
        self.pm = pm
        self.base_client = modules['base_client']
        self.base_engine = modules['base_engine']
        self.dwLocalPlayer = offsets['signatures']['dwLocalPlayer']
        self.dwGlowObjectManager = offsets['signatures']['dwGlowObjectManager']
        self.m_iTeamNum = offsets['netvars']['m_iTeamNum']
        self.model_ambient_min = offsets['signatures']['model_ambient_min']

    def get_class_id(self, entity):
        buffer = self.pm.read_int(entity + 8)
        buffer = self.pm.read_int(buffer + 2 * 4)
        buffer = self.pm.read_int(buffer + 1)
        return self.pm.read_int(buffer + 20)

    def get_entity_team(self, entity):
        return self.pm.read_int(entity + self.m_iTeamNum)

    def light_em_up(self):
        pointer = self.pm.read_int(self.base_engine + self.model_ambient_min - 44)
        xored = 1084227584 ^ pointer
        self.pm.write_int(self.base_engine + self.model_ambient_min, xored)

    def dye_em(self):
        glowmax = self.pm.read_int(self.base_client + self.dwGlowObjectManager + 4)
        glow_object = self.pm.read_int(self.base_client + self.dwGlowObjectManager)
        local_player = self.pm.read_int(self.base_client + self.dwLocalPlayer)
        local_player_team = self.get_entity_team(local_player)

        for i in range(glowmax):
            try:
                entity = self.pm.read_int(glow_object + 56 * i)
                if self.get_class_id(entity) == 40:
                    if self.get_entity_team(entity) != local_player_team:
                        self.pm.write_uchar(entity + 112, 255)
                        self.pm.write_uchar(entity + 113, 0)
                        self.pm.write_uchar(entity + 114, 255)

            except Exception as e:
                pass     

    def run(self):
        self.light_em_up()
        while True:
            self.dye_em()
            sleep(30)

class Aim():
    def __init__(self, pm, modules, offsets):
        self.pm = pm
        self.base_client = modules['base_client']
        self.base_engine = modules['base_engine']
        self.dwLocalPlayer = offsets['signatures']['dwLocalPlayer']
        self.dwClientState = offsets['signatures']['dwClientState']
        self.dwClientState_ViewAngles = offsets['signatures']['dwClientState_ViewAngles']
        self.m_dwBoneMatrix = offsets['netvars']['m_dwBoneMatrix']
        self.dwEntityList = offsets['signatures']['dwEntityList']
        self.m_iTeamNum = offsets['netvars']['m_iTeamNum']
        self.m_iHealth = offsets['netvars']['m_iHealth']
        self.m_vecOrigin = offsets['netvars']['m_vecOrigin']
        self.m_vecViewOffset = offsets['netvars']['m_vecViewOffset']
        self.m_bDormant = offsets['signatures']['m_bDormant']

    def fov(self, aim_pitch, aim_yaw, own_pitch, own_yaw, fov):
        if abs(own_pitch - aim_pitch) < fov:
            if (aim_yaw > 0 and own_yaw > 0) or (aim_yaw < 0 and own_yaw < 0):
                if abs(aim_yaw - own_yaw) < fov:
                    return True
                else:
                    if (360 - abs(aim_yaw - own_yaw)) < fov:
                        return True
        else:
            return False

    def rad2deg(self, angle):
        return angle * (180 / math.pi)

    def aim(self):
        local_player = self.pm.read_int(self.base_client + self.dwLocalPlayer)
        client_state = self.pm.read_int(self.base_engine + self.dwClientState)
        local_player_team = self.pm.read_int(local_player + self.m_iTeamNum)

        local_player_pitch = self.pm.read_float(client_state + self.dwClientState_ViewAngles)
        local_player_yaw = self.pm.read_float(client_state + self.dwClientState_ViewAngles + 4)

        local_x = self.pm.read_float(local_player + self.m_vecOrigin) + self.pm.read_float(local_player + self.m_vecViewOffset)
        local_y = self.pm.read_float(local_player + self.m_vecOrigin + 4) + self.pm.read_float(local_player + self.m_vecViewOffset + 4)
        local_z = self.pm.read_float(local_player + self.m_vecOrigin + 8) + self.pm.read_float(local_player + self.m_vecViewOffset + 8)

        for i in range(64):
            entity = self.pm.read_int(self.base_client + self.dwEntityList + i * 16)
            try:
                entity_team = self.pm.read_int(entity + self.m_iTeamNum)
                if entity_team != local_player_team and entity_team != 0:
                    if self.pm.read_int(entity + self.m_bDormant) == 0:
                        if self.pm.read_int(entity + self.m_iHealth) > 0:
                        
                            entity_bmatrix = self.pm.read_int(entity + self.m_dwBoneMatrix)

                            aim_x = self.pm.read_float(entity_bmatrix + (48 * _aimbone) + 12) - local_x
                            aim_y = self.pm.read_float(entity_bmatrix + (48 * _aimbone) + 28) - local_y
                            aim_z = entity_z = self.pm.read_float(entity_bmatrix + (48 * _aimbone) + 44) - local_z

                            #quick maths
                            aim_pitch = self.rad2deg(math.acos(aim_z / math.sqrt(math.pow(aim_x, 2) + math.pow(aim_y, 2) + math.pow(aim_z, 2)))) - 90
                            aim_yaw = self.rad2deg(math.atan2(aim_y, aim_x))
                            
                            if -89.0 < aim_pitch < 89.0 and -180.0 < aim_yaw < 180.0:
                                if self.fov(aim_pitch, aim_yaw, local_player_pitch, local_player_yaw, _fov):
                                    self.pm.write_float(client_state + self.dwClientState_ViewAngles, aim_pitch)
                                    self.pm.write_float(client_state + self.dwClientState_ViewAngles + 4, aim_yaw)
                                    return 0
                        
            except Exception as e:
                pass

    def run(self):
        key_pressed = False
        while True:
            if win32api.GetKeyState(1) == 0 or win32api.GetKeyState(1) == 1:
                key_pressed = False
            
            if (win32api.GetKeyState(1) == -127 or win32api.GetKeyState(1) == -128) and not key_pressed:
                self.aim()
                key_pressed = True

            sleep(0.01)

class Glow():
    def __init__(self, pm, modules, offsets):
        self.pm = pm
        self.base_client = modules['base_client']
        self.dwGlowObjectManager = offsets['signatures']['dwGlowObjectManager']
        self.dwLocalPlayer = offsets['signatures']['dwLocalPlayer']
        self.force_update_spectator_glow = offsets['signatures']['force_update_spectator_glow']
        self.m_iTeamNum = offsets['netvars']['m_iTeamNum']

    def get_class_id(self, entity):
        buffer = self.pm.read_int(entity + 8)
        buffer = self.pm.read_int(buffer + 2 * 4)
        buffer = self.pm.read_int(buffer + 1)
        return self.pm.read_int(buffer + 20)

    def glow_fix(self):
        #ghetto bytepatch in client.dll's .text section
        if self.pm.read_uchar(self.base_client + self.force_update_spectator_glow) == 116:
            self.pm.write_uchar(self.base_client + self.force_update_spectator_glow, 235)

    def get_entity_team(self, entity):
        return self.pm.read_int(entity + self.m_iTeamNum)

    def draw_glow(self, glow_object, i, r, g, b, a):
        self.pm.write_float(glow_object + 56 * i + 4, r)
        self.pm.write_float(glow_object + 56 * i + 8, g)
        self.pm.write_float(glow_object + 56 * i + 12, b)
        self.pm.write_float(glow_object + 56 * i + 16, a)
        self.pm.write_int(glow_object + 56 * i + 36, 1)
        self.pm.write_int(glow_object + 56 * i + 40, 0)

    def run(self):
        while True:
            try:
                self.glow_fix()
            
                glowmax = self.pm.read_int(self.base_client + self.dwGlowObjectManager + 4)
                glow_object = self.pm.read_int(self.base_client + self.dwGlowObjectManager)
                local_player = self.pm.read_int(self.base_client + self.dwLocalPlayer)
                local_player_team = self.get_entity_team(local_player)
            
                for i in range(glowmax):
                    try:
                        entity = self.pm.read_int(glow_object + 56 * i)
                        if (classid := self.get_class_id(entity)) == 40:
                            entity_team = self.get_entity_team(entity)
                            if entity_team != local_player_team and entity_team != 0:
                                self.draw_glow(glow_object, i, 0.0, 1.0, 0.502, 0.5)
                    except Exception as e:
                        pass
                        
            except Exception as e:
                pass

            sleep(0.2)

def main():
    while True:
        try:
            pm = pymem.Pymem('csgo.exe')
            p_handle = pm.process_handle
            base_client = pymem.process.module_from_name(p_handle, 'client.dll').lpBaseOfDll
            base_engine = pymem.process.module_from_name(p_handle, 'engine.dll').lpBaseOfDll
            break
        except:
            sleep(2)

    print('[@pyglue]\n')
    
    modules = {'base_client':base_client,
               'base_engine':base_engine}

    offsets = get_offsets()
    offsets_date = datetime.fromtimestamp(offsets['timestamp'])
    print(f'loaded offsets [{offsets_date}]')

    glow = Glow(pm, modules, offsets)
    aim = Aim(pm, modules, offsets)
    chams = Chams(pm, modules, offsets)
    
    with ThreadPoolExecutor() as executor:
        executor.submit(glow.run)
        executor.submit(aim.run)
        executor.submit(chams.run)

if __name__ == '__main__':
    main()

import pygame
import moderngl
import array
import math
import random
import sys
import json
import os
import urllib.request
import urllib.error

# JSONBin.io Configuration
JSONBIN_BIN_ID = "6afb8767ffd5d16053c6e846"
JSONBIN_API_KEY = "$2a$10$s3dxIZEmnCQobBS3pknLOOraXiYHnZieNiOgBpDuCLHjt3dVKO2Pe"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# Initialize Pygame and Mixer for Audio
pygame.init()
pygame.font.init()
pygame.mixer.init()

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# Retro Vector Color Palette
COLOR_BG = (10, 15, 20)
COLOR_GREEN = (0, 255, 102)
COLOR_CYAN = (0, 220, 255)
COLOR_AMBER = (255, 176, 0)
COLOR_RED = (255, 50, 50)
COLOR_WHITE = (240, 245, 255)
COLOR_DIM_GREEN = (0, 80, 30)
COLOR_GRID = (15, 30, 25)
COLOR_HOVER = (20, 50, 40)

HIGH_SCORE_FILE = "starship_highscores.json"

class Game:
    def __init__(self):
        # macOS OpenGL 3.3 Core Profile requirements
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, True)

        # Setup Pygame with OpenGL flags
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
        pygame.display.set_caption("SpaceX Starship Vector Lander (ModernGL CRT Edition)")
        self.clock = pygame.time.Clock()
        
        # ModernGL Context & Shaders
        self.ctx = moderngl.create_context()
        self.setup_opengl_pipeline()

        # Offscreen surface where Pygame renders the game 2D graphics
        self.game_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        try:
            self.font_sm = pygame.font.SysFont("Courier New", 16, bold=True)
            self.font_md = pygame.font.SysFont("Courier New", 20, bold=True)
            self.font_lg = pygame.font.SysFont("Courier New", 32, bold=True)
            self.font_xl = pygame.font.SysFont("Courier New", 48, bold=True)
        except:
            self.font_sm = pygame.font.Font(None, 24)
            self.font_md = pygame.font.Font(None, 32)
            self.font_lg = pygame.font.Font(None, 48)
            self.font_xl = pygame.font.Font(None, 64)

        self.state = "MENU"
        self.selected_level = 1
        
        # Settings
        self.scanlines_enabled = True
        self.audio_enabled = True
        
        # Load Audio Files
        self.sounds = {}
        self.thrust_channel = None
        self.is_thrust_playing = False
        self.load_audio()
        
        # High Scores
        self.high_scores = self.load_high_scores()
        
        # UI Clickable Zones & Hover Tracking
        self.menu_rects = []
        self.level_card_rects = []
        self.overlay_rects = []
        self.settings_rects = []
        self.back_button_rect = None
        
        self.current_hover_id = None
        self.frame_hover_id = None
        
        # Game session variables
        self.reset_game_state()

    def setup_opengl_pipeline(self):
        """Initializes ModernGL quad buffer, texture, and CRT shader program."""
        # Full-screen quad vertices (x, y, u, v)
        quad_vertices = array.array('f', [
            -1.0,  1.0, 0.0, 0.0,  # Top-Left
            -1.0, -1.0, 0.0, 1.0,  # Bottom-Left
             1.0, -1.0, 1.0, 1.0,  # Bottom-Right
            
            -1.0,  1.0, 0.0, 0.0,  # Top-Left
             1.0, -1.0, 1.0, 1.0,  # Bottom-Right
             1.0,  1.0, 1.0, 0.0,  # Top-Right
        ])
        self.quad_buffer = self.ctx.buffer(quad_vertices.tobytes())

        # GLSL Shaders for true Hardware CRT barrel distortion and scanlines
        vert_shader = """
            #version 330
            in vec2 in_vert;
            in vec2 in_text;
            out vec2 uv;
            void main() {
                gl_Position = vec4(in_vert, 0.0, 1.0);
                uv = in_text;
            }
        """

        frag_shader = """
            #version 330
            uniform sampler2D Tex;
            uniform int u_crt;
            in vec2 uv;
            out vec4 fragColor;

            void main() {
                vec2 coord = uv;
                if (u_crt == 1) {
                    // Fisheye / Barrel distortion math
                    vec2 cc = uv - 0.5;
                    float dist = dot(cc, cc);
                    coord = uv + cc * (dist * 0.22);
                    
                    // Check if pixel is outside the active 0.0 - 1.0 screen area
                    if (coord.x < 0.0 || coord.x > 1.0 || coord.y < 0.0 || coord.y > 1.0) {
                        // Calculate how far outside the screen edge this pixel is
                        float out_x = max(0.0 - coord.x, coord.x - 1.0);
                        float out_y = max(0.0 - coord.y, coord.y - 1.0);
                        float edge_dist = max(out_x, out_y);
                        
                        // Draw a metallic silver bezel hugging the outer curve (0.0 to 0.028)
                        if (edge_dist < 0.028) {
                            // Subtle 3D shading across the bezel thickness
                            float shade = 1.0 - (edge_dist / 0.028) * 0.45;
                            // Slight directional lighting highlight from the top-left
                            float highlight = (1.0 - uv.y) * 0.15 + (1.0 - uv.x) * 0.1;
                            vec3 silver = vec3(0.68, 0.71, 0.75) * shade + vec3(highlight);
                            fragColor = vec4(silver, 1.0);
                        } else {
                            // Pitch black beyond the silver frame
                            fragColor = vec4(0.0, 0.0, 0.0, 1.0);
                        }
                        return;
                    }
                }
                
                vec3 color;
                if (u_crt == 1) {
                    // Chromatic aberration (splitting RGB channels near edges)
                    float r = texture(Tex, coord + vec2(0.0025, 0.0)).r;
                    float g = texture(Tex, coord).g;
                    float b = texture(Tex, coord - vec2(0.0025, 0.0)).b;
                    
                    // Curved Scanline effect
                    float scanline = sin(coord.y * 900.0) * 0.09;
                    color = vec3(r, g, b) - scanline;
                    
                    // Vignette shading
                    color *= (1.0 - dot(coord - 0.5, coord - 0.5) * 1.5);
                } else {
                    color = texture(Tex, coord).rgb;
                }
                
                fragColor = vec4(color, 1.0);
            }
        """

        self.prog = self.ctx.program(vertex_shader=vert_shader, fragment_shader=frag_shader)
        self.vao = self.ctx.vertex_array(self.prog, [(self.quad_buffer, '2f 2f', 'in_vert', 'in_text')])

        # Create OpenGL texture for Pygame surface transfer
        self.texture = self.ctx.texture((SCREEN_WIDTH, SCREEN_HEIGHT), 3, data=None)
        self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)

    def load_audio(self):
        sound_files = {
            "thrust": resource_path("thrust.wav"),
            "crash": resource_path("freesound_community-8-bit-explosion-low-resonant-45659.mp3"),
            "success": resource_path("success.wav"),
            "menu_select": resource_path("chisper-8-bit-menu-select-634748.mp3")
        }
        
        for name, filename in sound_files.items():
            if os.path.exists(filename):
                self.sounds[name] = pygame.mixer.Sound(filename)
                if name == "thrust":
                    self.sounds[name].set_volume(0.4)
            else:
                print(f"Warning: Audio file '{filename}' not found. Skipping.")

    def play_sound(self, sound_type):
        if not self.audio_enabled or sound_type not in self.sounds:
            return
            
        if sound_type == "thrust":
            self.thrust_channel = self.sounds["thrust"].play(loops=-1)
        else:
            self.sounds[sound_type].play()

    def stop_sound(self, sound_type):
        if sound_type == "thrust" and self.thrust_channel:
            self.thrust_channel.stop()

    def load_high_scores(self):
        headers = {
            "X-Access-Key": JSONBIN_API_KEY,
            "User-Agent": "StarshipLander/1.0"
        }
        try:
            req = urllib.request.Request(f"{JSONBIN_URL}/latest", headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("record", {"1": [], "2": [], "3": []})
        except Exception as e:
            print(f"Offline or failed to fetch high scores: {e}")
            return {"1": [], "2": [], "3": []}

    def save_high_scores(self):
        headers = {
            "Content-Type": "application/json",
            "X-Access-Key": JSONBIN_API_KEY,
            "User-Agent": "StarshipLander/1.0"
        }
        try:
            payload = json.dumps(self.high_scores).encode("utf-8")
            req = urllib.request.Request(JSONBIN_URL, data=payload, headers=headers, method="PUT")
            with urllib.request.urlopen(req, timeout=4) as response:
                pass
        except Exception as e:
            print(f"Failed to save high scores online: {e}")

    def save_high_scores(self):
        try:
            with open(HIGH_SCORE_FILE, "w") as f:
                json.dump(self.high_scores, f)
        except:
            pass

    def reset_game_state(self):
        self.ship_x = 2000 if self.selected_level == 2 else (1500 if self.selected_level == 3 else 1000)
        self.ship_y = 150
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0
        self.fuel = 1000.0
        self.max_fuel = 1000.0
        self.score = 0
        self.elapsed_time = 0.0
        self.thrusting = False
        
        if self.is_thrust_playing:
            self.stop_sound("thrust")
            self.is_thrust_playing = False
        
        if self.selected_level == 1:
            self.world_width = 2000
            self.pad_x = 1000
            self.pad_y = 720
            self.pad_w = 120
        elif self.selected_level == 2:
            self.world_width = 3000
            self.pad_x = 1500
            self.base_pad_y = 720
            self.pad_w = 140
            self.wave_time = 0.0
        elif self.selected_level == 3:
            self.world_width = 2400
            self.tower_x = 1200
            self.tower_y = 750
            self.pad_x = 1200
            self.pad_y = 320
            self.pad_w = 90
            self.chopstick_progress = 0.0

        self.camera_x = max(0, min(self.ship_x - SCREEN_WIDTH / 2, self.world_width - SCREEN_WIDTH))
        self.last_result = None
        self.new_score_entry = {"score": 0, "level": self.selected_level, "name": ""}
        
        self.overlay_rects = []
        self.settings_rects = []
        self.back_button_rect = None

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouseclick(event)

            if self.state == "PLAYING":
                self.update_playing(dt)

            self.render_frame()
            
        pygame.quit()
        sys.exit()

    def handle_mouseclick(self, event):
        if event.button == 1: 
            if self.state == "MENU":
                for item in self.menu_rects:
                    if item["rect"].collidepoint(event.pos):
                        if item["action"] == "QUIT":
                            pygame.quit()
                            sys.exit()
                        else:
                            self.state = item["action"]
                            
            elif self.state == "LEVEL_SELECT":
                for card in self.level_card_rects:
                    if card["rect"].collidepoint(event.pos):
                        self.selected_level = card["level"]
                        self.reset_game_state()
                        self.state = "PLAYING"
                if self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                    self.state = "MENU"

            elif self.state == "SETTINGS":
                for item in self.settings_rects:
                    if item["rect"].collidepoint(event.pos):
                        if item["action"] == "TOGGLE_SCANLINES":
                            self.scanlines_enabled = not self.scanlines_enabled
                        elif item["action"] == "TOGGLE_AUDIO":
                            self.audio_enabled = not self.audio_enabled
                            if not self.audio_enabled and self.is_thrust_playing:
                                self.stop_sound("thrust")
                                self.is_thrust_playing = False
                if self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                    self.state = "MENU"

            elif self.state == "HIGHSCORES":
                if self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                    self.state = "MENU"

            elif self.state in ["SUCCESS", "CRASH"]:
                for item in self.overlay_rects:
                    if item["rect"].collidepoint(event.pos):
                        if item["action"] == "RETRY":
                            self.reset_game_state()
                            self.state = "PLAYING"
                        elif item["action"] == "MENU":
                            self.state = "MENU"

    def handle_keydown(self, event):
        if self.state == "NAME_INPUT":
            if event.key == pygame.K_RETURN:
                if len(self.new_score_entry["name"].strip()) > 0:
                    lvl_key = str(self.selected_level)
                    self.high_scores[lvl_key].append(self.new_score_entry)
                    self.high_scores[lvl_key] = sorted(self.high_scores[lvl_key], key=lambda x: x["score"], reverse=True)[:5]
                    self.save_high_scores()
                self.state = "HIGHSCORES"
            elif event.key == pygame.K_BACKSPACE:
                self.new_score_entry["name"] = self.new_score_entry["name"][:-1]
            else:
                if len(self.new_score_entry["name"]) < 3 and event.unicode.isalnum():
                    self.new_score_entry["name"] += event.unicode.upper()
            return

        if event.key == pygame.K_ESCAPE:
            if self.state in ["PLAYING", "SUCCESS", "CRASH"]:
                self.state = "MENU"
                if self.is_thrust_playing:
                    self.stop_sound("thrust")
                    self.is_thrust_playing = False
            elif self.state in ["LEVEL_SELECT", "SETTINGS", "HIGHSCORES"]:
                self.state = "MENU"

    def update_playing(self, dt):
        self.elapsed_time += dt
        keys = pygame.key.get_pressed()
        
        rotation_speed = 3.0 * dt
        thrust_power = 650.0 * dt
        gravity = 140.0 * dt

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.angle -= rotation_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.angle += rotation_speed

        self.thrusting = False
        if (keys[pygame.K_UP] or keys[pygame.K_w]) and self.fuel > 0:
            if not (keys[pygame.K_DOWN] or keys[pygame.K_s]): 
                self.vx += math.sin(self.angle) * thrust_power
                self.vy -= math.cos(self.angle) * thrust_power
                self.fuel = max(0.0, self.fuel - 45.0 * dt)
                self.thrusting = True
        
        if self.thrusting and not self.is_thrust_playing:
            self.play_sound("thrust")
            self.is_thrust_playing = True
        elif not self.thrusting and self.is_thrust_playing:
            self.stop_sound("thrust")
            self.is_thrust_playing = False
            
        self.vy += gravity
        self.ship_x += self.vx * dt
        self.ship_y += self.vy * dt

        if self.selected_level == 2:
            self.wave_time += dt * 3.0
            current_pad_y = self.base_pad_y + math.sin(self.wave_time) * 15.0
        else:
            current_pad_y = self.pad_y

        target_camera_x = self.ship_x - SCREEN_WIDTH / 2
        self.camera_x += (target_camera_x - self.camera_x) * 10.0 * dt
        self.camera_x = max(0, min(self.camera_x, self.world_width - SCREEN_WIDTH))

        ship_screen_x = self.ship_x - self.camera_x
        if ship_screen_x < 0 or ship_screen_x > SCREEN_WIDTH:
            self.trigger_crash("LOST IN ORBIT / OFFSCREEN")
            return

        floor_y = current_pad_y if (self.selected_level != 3) else (self.tower_y - 20)
        
        if self.selected_level == 3:
            dist_to_tower_center = abs(self.ship_x - self.tower_x)
            if self.ship_y >= current_pad_y - 20 and self.ship_y <= current_pad_y + 30:
                if dist_to_tower_center < self.pad_w / 2:
                    speed = math.hypot(self.vx, self.vy)
                    angle_deg = abs(math.degrees(self.angle)) % 360
                    if angle_deg > 180: angle_deg = 360 - angle_deg
                    
                    if speed < 85 and angle_deg < 15 and abs(self.vx) < 40 and abs(self.vy) < 60:
                        self.chopstick_progress = min(1.0, self.chopstick_progress + dt * 2.0)
                        if self.chopstick_progress >= 1.0:
                            self.ship_x = self.tower_x
                            self.ship_y = current_pad_y - 12 
                            self.vx = 0
                            self.vy = 0
                            self.angle = 0
                            self.trigger_success()
                            return
                    else:
                        self.trigger_crash("IMPACT WITH TOWER CHOPSTICKS")
                        return

        if self.ship_y >= floor_y - 25: 
            if self.selected_level != 3:
                pad_left = self.pad_x - self.pad_w / 2
                pad_right = self.pad_x + self.pad_w / 2
                
                if pad_left <= self.ship_x <= pad_right:
                    speed = math.hypot(self.vx, self.vy)
                    angle_deg = abs(math.degrees(self.angle)) % 360
                    if angle_deg > 180: angle_deg = 360 - angle_deg
                    
                    if speed < 90 and angle_deg < 12 and abs(self.vx) < 50 and abs(self.vy) < 70:
                        self.ship_y = floor_y - 24 
                        self.vx = 0
                        self.vy = 0
                        self.angle = 0
                        self.trigger_success()
                        return
                    else:
                        self.trigger_crash("HARD TOUCHDOWN / HIGH VELOCITY")
                        return
                else:
                    self.trigger_crash("MISSED LANDING PAD")
                    return
            else:
                if self.ship_y >= self.tower_y - 20:
                    self.trigger_crash("CRASHED INTO GROUND")
                    return

    def trigger_success(self):
        self.state = "SUCCESS"
        self.stop_sound("thrust")
        self.is_thrust_playing = False
        self.play_sound("success")
        
        base_points = 1000 if self.selected_level == 1 else (1500 if self.selected_level == 2 else 2000)
        fuel_bonus = int(self.fuel * 2)
        time_bonus = max(0, int((60 - self.elapsed_time) * 10))
        self.score = base_points + fuel_bonus + time_bonus
        
        lvl_key = str(self.selected_level)
        current_scores = self.high_scores[lvl_key]
        is_high_score = len(current_scores) < 5 or self.score > current_scores[-1]["score"]
        
        if is_high_score:
            self.new_score_entry = {"score": self.score, "level": self.selected_level, "name": ""}
            self.state = "NAME_INPUT"

    def trigger_crash(self, reason):
        self.state = "CRASH"
        self.stop_sound("thrust")
        self.is_thrust_playing = False
        self.play_sound("crash")
        
        self.last_result = reason
        self.score = 0

    def render_frame(self):
        # 1. Draw 2D Game / Menu graphics onto Pygame offscreen surface
        self.game_surface.fill(COLOR_BG)
        self.frame_hover_id = None
        
        if self.state in ["MENU", "LEVEL_SELECT", "SETTINGS", "HIGHSCORES"]:
            self.draw_menu_system()
        elif self.state in ["PLAYING", "SUCCESS", "CRASH", "NAME_INPUT"]:
            self.draw_game_scene()
            if self.state == "SUCCESS":
                self.draw_overlay_message("SUCCESSFUL LANDING!", COLOR_GREEN, [("PLAY AGAIN", "RETRY"), ("MAIN MENU", "MENU")])
            elif self.state == "CRASH":
                self.draw_overlay_message(f"MISSION FAILED: {self.last_result}", COLOR_RED, [("RETRY MISSION", "RETRY"), ("MAIN MENU", "MENU")])
            elif self.state == "NAME_INPUT":
                self.draw_name_input_overlay()

        # Play audio chirp if hover state changed
        if self.frame_hover_id != self.current_hover_id:
            if self.frame_hover_id is not None:
                self.play_sound("menu_select")
            self.current_hover_id = self.frame_hover_id

        # 2. Push Pygame surface into ModernGL Texture
        view = pygame.image.tostring(self.game_surface, "RGB", False)
        self.texture.write(view)

        # 3. Render via ModernGL Shader (applying GPU hardware CRT fisheye/distortion)
        self.ctx.clear(0.0, 0.0, 0.0)
        self.texture.use(0)
        self.prog['Tex'] = 0
        self.prog['u_crt'].value = 1 if self.scanlines_enabled else 0
        self.vao.render(moderngl.TRIANGLES)

        pygame.display.flip()

    def draw_back_button(self, mouse_pos):
        temp_surf = self.font_md.render("BACK TO MAIN MENU", True, COLOR_WHITE)
        self.back_button_rect = temp_surf.get_rect(center=(SCREEN_WIDTH // 2, 700))
        
        is_hovered = self.back_button_rect.collidepoint(mouse_pos)
        if is_hovered:
            self.frame_hover_id = "back_button"
            pygame.draw.rect(self.game_surface, COLOR_HOVER, self.back_button_rect.inflate(40, 20))
            pygame.draw.rect(self.game_surface, COLOR_GREEN, self.back_button_rect.inflate(40, 20), 2)
            c = COLOR_GREEN
        else:
            c = COLOR_AMBER
            
        btn_surf = self.font_md.render("BACK TO MAIN MENU", True, c)
        self.game_surface.blit(btn_surf, self.back_button_rect)

    def draw_menu_system(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for x in range(0, SCREEN_WIDTH, 60):
            pygame.draw.line(self.game_surface, COLOR_GRID, (x, 0), (x, SCREEN_HEIGHT), 1)
        for y in range(0, SCREEN_HEIGHT, 60):
            pygame.draw.line(self.game_surface, COLOR_GRID, (0, y), (SCREEN_WIDTH, y), 1)

        title_surf = self.font_xl.render("SPACEX STARSHIP", True, COLOR_CYAN)
        subtitle_surf = self.font_lg.render("VECTOR LANDER", True, COLOR_WHITE)
        self.game_surface.blit(title_surf, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2, 80))
        self.game_surface.blit(subtitle_surf, (SCREEN_WIDTH // 2 - subtitle_surf.get_width() // 2, 140))

        if self.state == "MENU":
            menu_options = [
                {"text": "LEVEL SELECTION", "action": "LEVEL_SELECT"},
                {"text": "HIGH SCORES", "action": "HIGHSCORES"},
                {"text": "SETTINGS", "action": "SETTINGS"},
                {"text": "QUIT GAME", "action": "QUIT"}
            ]
            
            self.menu_rects = []
            start_y = 280
            
            for option in menu_options:
                temp_surf = self.font_lg.render(option["text"], True, COLOR_WHITE)
                rect = temp_surf.get_rect(center=(SCREEN_WIDTH // 2, start_y))
                
                is_hovered = rect.collidepoint(mouse_pos)
                if is_hovered:
                    self.frame_hover_id = f"menu_{option['action']}"
                    pygame.draw.rect(self.game_surface, COLOR_HOVER, rect.inflate(40, 20))
                    pygame.draw.rect(self.game_surface, COLOR_GREEN, rect.inflate(40, 20), 2)
                    color = COLOR_GREEN
                else:
                    color = COLOR_WHITE
                
                txt_surf = self.font_lg.render(option["text"], True, color)
                self.game_surface.blit(txt_surf, rect)
                
                self.menu_rects.append({"rect": rect, "action": option["action"]})
                start_y += 85

        elif self.state == "LEVEL_SELECT":
            sub_title = self.font_md.render("SELECT MISSION (CLICK TO LAUNCH)", True, COLOR_AMBER)
            self.game_surface.blit(sub_title, (SCREEN_WIDTH // 2 - sub_title.get_width() // 2, 160))
            
            self.level_card_rects = []
            card_w, card_h = 320, 360
            start_x = 100
            y_pos = 240
            
            for i in range(1, 4):
                x_pos = start_x + (i - 1) * 360
                card_rect = pygame.Rect(x_pos, y_pos, card_w, card_h)
                
                is_hovered = card_rect.collidepoint(mouse_pos)
                if is_hovered:
                    self.frame_hover_id = f"level_{i}"
                    box_color = COLOR_GREEN
                    line_thick = 3
                    pygame.draw.rect(self.game_surface, COLOR_HOVER, card_rect)
                else:
                    box_color = COLOR_DIM_GREEN
                    line_thick = 2
                    
                pygame.draw.rect(self.game_surface, box_color, card_rect, line_thick)
                
                preview_surf = pygame.Surface((card_w - 20, 200))
                preview_surf.fill(COLOR_BG)
                self.draw_mini_preview(i, preview_surf)
                self.game_surface.blit(preview_surf, (x_pos + 10, y_pos + 10))
                
                lbl_color = COLOR_GREEN if is_hovered else COLOR_CYAN
                lbl = self.font_md.render(f"Mission {i}", True, lbl_color)
                self.game_surface.blit(lbl, (x_pos + 20, y_pos + 220))
                
                desc = "Ground Pad Landing" if i == 1 else ("Sea Drone Ship" if i == 2 else "Mechazilla Tower Catch")
                d_lbl = self.font_sm.render(desc, True, COLOR_WHITE)
                self.game_surface.blit(d_lbl, (x_pos + 20, y_pos + 260))
                
                self.level_card_rects.append({"rect": card_rect, "level": i})

            self.draw_back_button(mouse_pos)

        elif self.state == "SETTINGS":
            sub_title = self.font_md.render("GAME SETTINGS", True, COLOR_AMBER)
            self.game_surface.blit(sub_title, (SCREEN_WIDTH // 2 - sub_title.get_width() // 2, 220))
            
            self.settings_rects = []
            
            scan_status = "ENABLED" if self.scanlines_enabled else "DISABLED"
            scan_text = f"GPU CRT & Fisheye: {scan_status}"
            temp_surf1 = self.font_md.render(scan_text, True, COLOR_WHITE)
            rect1 = temp_surf1.get_rect(center=(SCREEN_WIDTH // 2, 320))
            
            if rect1.collidepoint(mouse_pos):
                self.frame_hover_id = "settings_scanlines"
                pygame.draw.rect(self.game_surface, COLOR_HOVER, rect1.inflate(40, 20))
                pygame.draw.rect(self.game_surface, COLOR_GREEN, rect1.inflate(40, 20), 2)
                c1 = COLOR_GREEN
            else:
                c1 = COLOR_GREEN if self.scanlines_enabled else COLOR_RED
                
            surf1 = self.font_md.render(scan_text, True, c1)
            self.game_surface.blit(surf1, rect1)
            self.settings_rects.append({"rect": rect1, "action": "TOGGLE_SCANLINES"})
            
            audio_status = "ON" if self.audio_enabled else "OFF"
            audio_text = f"Audio & Effects:    {audio_status}"
            temp_surf2 = self.font_md.render(audio_text, True, COLOR_WHITE)
            rect2 = temp_surf2.get_rect(center=(SCREEN_WIDTH // 2, 400))
            
            if rect2.collidepoint(mouse_pos):
                self.frame_hover_id = "settings_audio"
                pygame.draw.rect(self.game_surface, COLOR_HOVER, rect2.inflate(40, 20))
                pygame.draw.rect(self.game_surface, COLOR_GREEN, rect2.inflate(40, 20), 2)
                c2 = COLOR_GREEN
            else:
                c2 = COLOR_GREEN if self.audio_enabled else COLOR_RED
                
            surf2 = self.font_md.render(audio_text, True, c2)
            self.game_surface.blit(surf2, rect2)
            self.settings_rects.append({"rect": rect2, "action": "TOGGLE_AUDIO"})
            
            self.draw_back_button(mouse_pos)

        elif self.state == "HIGHSCORES":
            sub_title = self.font_md.render("HIGH SCORES (TOP 5 PER LEVEL)", True, COLOR_AMBER)
            self.game_surface.blit(sub_title, (SCREEN_WIDTH // 2 - sub_title.get_width() // 2, 220))
            
            start_x = 120
            for i in range(1, 4):
                x_pos = start_x + (i - 1) * 360
                pygame.draw.rect(self.game_surface, COLOR_DIM_GREEN, (x_pos, 280, 300, 360), 1)
                
                lvl_title = self.font_md.render(f"Mission {i}", True, COLOR_CYAN)
                self.game_surface.blit(lvl_title, (x_pos + 20, 300))
                
                scores = self.high_scores.get(str(i), [])
                y_off = 350
                if not scores:
                    no_sc = self.font_sm.render("No records yet", True, COLOR_WHITE)
                    self.game_surface.blit(no_sc, (x_pos + 20, y_off))
                else:
                    for rank, entry in enumerate(scores, 1):
                        sc_txt = self.font_sm.render(f"{rank}. {entry['name']} - {entry['score']}", True, COLOR_GREEN)
                        self.game_surface.blit(sc_txt, (x_pos + 20, y_off))
                        y_off += 40

            self.draw_back_button(mouse_pos)

    def draw_mini_preview(self, level_id, surf):
        w, h = surf.get_width(), surf.get_height()
        pygame.draw.rect(surf, COLOR_GRID, (0, 0, w, h), 1)
        
        if level_id == 1:
            pygame.draw.line(surf, COLOR_GREEN, (10, h - 30), (w - 10, h - 30), 2)
            pygame.draw.rect(surf, COLOR_CYAN, (w//2 - 25, h - 35, 50, 10))
            pygame.draw.line(surf, COLOR_WHITE, (w//2, 40), (w//2 - 10, h - 70), 1)
            pygame.draw.line(surf, COLOR_WHITE, (w//2, 40), (w//2 + 10, h - 70), 1)
        elif level_id == 2:
            for x in range(10, w - 10, 15):
                pygame.draw.arc(surf, COLOR_CYAN, (x, h - 45, 20, 15), 0, 3.14, 1)
            pygame.draw.rect(surf, COLOR_AMBER, (w//2 - 30, h - 30, 60, 8))
            pygame.draw.line(surf, COLOR_WHITE, (w//2, 50), (w//2 - 10, h - 70), 1)
            pygame.draw.line(surf, COLOR_WHITE, (w//2, 50), (w//2 + 10, h - 70), 1)
        elif level_id == 3:
            pygame.draw.line(surf, COLOR_GREEN, (10, h - 20), (w - 10, h - 20), 2)
            pygame.draw.rect(surf, COLOR_AMBER, (w//2 - 15, 60, 30, h - 80), 2)
            pygame.draw.line(surf, COLOR_RED, (w//2 - 40, h//2), (w//2, h//2), 2)
            pygame.draw.line(surf, COLOR_RED, (w//2 + 40, h//2), (w//2, h//2), 2)
            pygame.draw.line(surf, COLOR_WHITE, (w//2, 20), (w//2 - 6, 80), 1)
            pygame.draw.line(surf, COLOR_WHITE, (w//2, 20), (w//2 + 6, 80), 1)

    def draw_game_scene(self):
        cam_offset_x = int(self.camera_x)
        
        if self.selected_level == 1:
            pygame.draw.line(self.game_surface, COLOR_GREEN, (-cam_offset_x, 720), (self.world_width - cam_offset_x, 720), 2)
            pad_screen_x = self.pad_x - cam_offset_x
            pygame.draw.rect(self.game_surface, COLOR_CYAN, (pad_screen_x - self.pad_w // 2, 715, self.pad_w, 10), 2)
            pygame.draw.line(self.game_surface, COLOR_WHITE, (pad_screen_x - 15, 715), (pad_screen_x + 15, 715), 3)

        elif self.selected_level == 2:
            pygame.draw.line(self.game_surface, COLOR_DIM_GREEN, (-cam_offset_x, 740), (self.world_width - cam_offset_x, 740), 1)
            for wx in range(-cam_offset_x, self.world_width - cam_offset_x, 30):
                wave_y = 740 + math.sin(self.wave_time + wx * 0.05) * 12.0
                pygame.draw.arc(self.game_surface, COLOR_CYAN, (wx, int(wave_y), 30, 15), 0, 3.14, 2)
            
            current_pad_y = self.base_pad_y + math.sin(self.wave_time) * 15.0
            pad_screen_x = self.pad_x - cam_offset_x
            pygame.draw.rect(self.game_surface, COLOR_AMBER, (pad_screen_x - self.pad_w // 2, int(current_pad_y), self.pad_w, 12), 2)

        elif self.selected_level == 3:
            pygame.draw.line(self.game_surface, COLOR_GREEN, (-cam_offset_x, self.tower_y), (self.world_width - cam_offset_x, self.tower_y), 2)
            tower_screen_x = self.tower_x - cam_offset_x
            pygame.draw.rect(self.game_surface, COLOR_AMBER, (tower_screen_x - 25, self.pad_y, 50, self.tower_y - self.pad_y), 2)
            
            arm_len = int(45 * (1.0 - self.chopstick_progress))
            pygame.draw.line(self.game_surface, COLOR_RED, (tower_screen_x - 25 - arm_len, self.pad_y + 10), (tower_screen_x, self.pad_y + 10), 3)
            pygame.draw.line(self.game_surface, COLOR_RED, (tower_screen_x + 25 + arm_len, self.pad_y + 10), (tower_screen_x, self.pad_y + 10), 3)

        self.draw_starship()
        self.draw_hud()

        ship_screen_x = self.ship_x - self.camera_x
        if ship_screen_x < 50:
            pygame.draw.polygon(self.game_surface, COLOR_AMBER, [(20, self.ship_y), (40, self.ship_y - 10), (40, self.ship_y + 10)])
        elif ship_screen_x > SCREEN_WIDTH - 50:
            pygame.draw.polygon(self.game_surface, COLOR_AMBER, [(SCREEN_WIDTH - 20, self.ship_y), (SCREEN_WIDTH - 40, self.ship_y - 10), (SCREEN_WIDTH - 40, self.ship_y + 10)])

    def draw_starship(self):
        ship_screen_x = self.ship_x - self.camera_x
        
        points = [
            (0, -30),   
            (8, -10),   
            (10, 20),   
            (14, 28),   
            (4, 24),
            (-4, 24),
            (-14, 28),  
            (-10, 20),  
            (-8, -10),  
        ]
        
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        
        transformed_points = []
        for px, py in points:
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            transformed_points.append((ship_screen_x + rx, self.ship_y + ry))
            
        pygame.draw.polygon(self.game_surface, COLOR_WHITE, transformed_points, 2)
        
        if self.thrusting:
            flame_len = random.randint(15, 25)
            fx = ship_screen_x - math.sin(self.angle) * (28 + flame_len)
            fy = self.ship_y + math.cos(self.angle) * (28 + flame_len)
            pygame.draw.line(self.game_surface, COLOR_CYAN, (ship_screen_x - math.sin(self.angle)*25, self.ship_y + math.cos(self.angle)*25), (fx, fy), 3)

    def draw_hud(self):
        pygame.draw.rect(self.game_surface, COLOR_DIM_GREEN, (20, 20, SCREEN_WIDTH - 40, 70), 1)
        
        sc_txt = self.font_sm.render(f"SCORE: {int(self.score)}", True, COLOR_GREEN)
        time_txt = self.font_sm.render(f"TIME: {self.elapsed_time:.1f}s", True, COLOR_WHITE)
        fuel_txt = self.font_sm.render(f"FUEL: {int(self.fuel)}/{int(self.max_fuel)}", True, COLOR_AMBER if self.fuel > 200 else COLOR_RED)
        
        self.game_surface.blit(sc_txt, (40, 35))
        self.game_surface.blit(time_txt, (220, 35))
        self.game_surface.blit(fuel_txt, (380, 35))

        altitude = max(0, int(720 - self.ship_y)) if self.selected_level != 3 else max(0, int(self.tower_y - self.ship_y))
        
        h_dir = ">" if self.vx > 0 else ("<" if self.vx < 0 else " ")
        v_dir = "v" if self.vy > 0 else ("^" if self.vy < 0 else " ")
        
        h_spd_txt = self.font_sm.render(f"H-SPD: {abs(self.vx):.1f} {h_dir}", True, COLOR_CYAN)
        v_spd_txt = self.font_sm.render(f"V-SPD: {abs(self.vy):.1f} {v_dir}", True, COLOR_CYAN)
        alt_txt = self.font_sm.render(f"ALT: {altitude}", True, COLOR_GREEN)
        
        self.game_surface.blit(h_spd_txt, (560, 35))
        self.game_surface.blit(v_spd_txt, (780, 35))
        self.game_surface.blit(alt_txt, (1000, 35))

        controls_txt = self.font_sm.render("CONTROLS: WASD / Arrow Keys = Steer & Thrust", True, COLOR_DIM_GREEN)
        self.game_surface.blit(controls_txt, (20, SCREEN_HEIGHT - 35))

    def draw_overlay_message(self, message, color, options):
        mouse_pos = pygame.mouse.get_pos()
        
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 15, 20, 220))
        self.game_surface.blit(overlay, (0, 0))
        
        msg_surf = self.font_lg.render(message, True, color)
        self.game_surface.blit(msg_surf, (SCREEN_WIDTH // 2 - msg_surf.get_width() // 2, SCREEN_HEIGHT // 2 - 100))
        
        if self.state in ["SUCCESS", "CRASH"]:
            sc_surf = self.font_md.render(f"Final Score: {int(self.score)}", True, COLOR_WHITE)
            self.game_surface.blit(sc_surf, (SCREEN_WIDTH // 2 - sc_surf.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
            
        y_off = SCREEN_HEIGHT // 2 + 40
        self.overlay_rects = []
        
        for opt_text, opt_action in options:
            temp_surf = self.font_md.render(opt_text, True, COLOR_WHITE)
            rect = temp_surf.get_rect(center=(SCREEN_WIDTH // 2, y_off))
            
            is_hovered = rect.collidepoint(mouse_pos)
            if is_hovered:
                self.frame_hover_id = f"overlay_{opt_action}"
                pygame.draw.rect(self.game_surface, COLOR_HOVER, rect.inflate(40, 20))
                pygame.draw.rect(self.game_surface, COLOR_GREEN, rect.inflate(40, 20), 2)
                lbl_color = COLOR_GREEN
            else:
                lbl_color = COLOR_CYAN
                
            opt_surf = self.font_md.render(opt_text, True, lbl_color)
            self.game_surface.blit(opt_surf, rect)
            self.overlay_rects.append({"rect": rect, "action": opt_action})
            y_off += 70

    def draw_name_input_overlay(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 15, 20, 235))
        self.game_surface.blit(overlay, (0, 0))
        
        title = self.font_lg.render("NEW HIGH SCORE!", True, COLOR_AMBER)
        self.game_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 120))
        
        score_txt = self.font_md.render(f"Score: {int(self.score)}", True, COLOR_GREEN)
        self.game_surface.blit(score_txt, (SCREEN_WIDTH // 2 - score_txt.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
        
        prompt_txt = self.font_md.render("ENTER YOUR 3-LETTER INITIALS:", True, COLOR_WHITE)
        self.game_surface.blit(prompt_txt, (SCREEN_WIDTH // 2 - prompt_txt.get_width() // 2, SCREEN_HEIGHT // 2))
        
        name_box = self.font_lg.render(f"[ {self.new_score_entry['name']}_ ]", True, COLOR_CYAN)
        self.game_surface.blit(name_box, (SCREEN_WIDTH // 2 - name_box.get_width() // 2, SCREEN_HEIGHT // 2 + 50))
        
        inst_txt = self.font_sm.render("Type initials and press [ENTER]", True, COLOR_AMBER)
        self.game_surface.blit(inst_txt, (SCREEN_WIDTH // 2 - inst_txt.get_width() // 2, SCREEN_HEIGHT // 2 + 120))

if __name__ == "__main__":
    game = Game()
    game.run()
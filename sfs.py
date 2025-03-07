import pygame
import random
import math
import sys
import json
import os

SETTINGS_FILE = "settings.json"

with open(SETTINGS_FILE, "r") as f:
    config = json.load(f)

# Window settings
WIN_WIDTH = config["window"]["width"]
WIN_HEIGHT = config["window"]["height"]
FPS = config["window"]["fps"]

# Basic colors (for fallback or UI)
COLOR_BLACK = tuple(config["colors"]["BLACK"])
COLOR_WHITE = tuple(config["colors"]["WHITE"])

pygame.init()
pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))


pygame.mixer.init()

bg_music_path = config.get("audio", {}).get("bg_music_path", "")
sound_effects_config = config.get("audio", {}).get("effects", {})

# Load SFX into a dictionary
sound_effects = {}
for sfx_name, sfx_path in sound_effects_config.items():
    if os.path.isfile(sfx_path):
        sound_effects[sfx_name] = pygame.mixer.Sound(sfx_path)
    else:
        sound_effects[sfx_name] = None
        print(f"Warning: Sound effect file {sfx_path} not found for '{sfx_name}'")

# Loop background music if path is valid
if bg_music_path and os.path.isfile(bg_music_path):
    pygame.mixer.music.load(bg_music_path)
    pygame.mixer.music.play(-1)  # loop forever
else:
    print("Warning: No valid background music path provided in settings.")

# -----------------------------------------------------------------------------
# SPRITE LOADING
# -----------------------------------------------------------------------------
def load_sprites_from_config(sprite_conf):
    loaded = {}
    for sprite_name, info in sprite_conf.items():
        path = info.get("path", "")
        scale = info.get("scale", [32, 32])
        offset = info.get("offset", [16, 16])
        z_order = info.get("z_order", 0)

        if path and os.path.isfile(path):
            surf = pygame.image.load(path).convert_alpha()
            if scale:
                w, h = scale
                surf = pygame.transform.scale(surf, (w, h))
        else:
            w, h = scale
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill((255, 0, 255, 128))
            print(f"Warning: Sprite file not found or missing path for '{sprite_name}' -> using fallback")

        loaded[sprite_name] = {
            "surface": surf,
            "offset": tuple(offset),
            "z_order": z_order
        }
    return loaded

sprite_conf = config.get("sprites", {})
loaded_sprites = load_sprites_from_config(sprite_conf)

# -----------------------------------------------------------------------------
# GAME CLASSES
# -----------------------------------------------------------------------------
class Player:
    def __init__(self):
        p = config["player"]
        self.radius = p["radius"]
        self.x = WIN_WIDTH // 2
        self.y = WIN_HEIGHT // 2
        self.health = p["initial_health"]
        self.color = tuple(p["color"])
        self.fire_delay = p["fire_delay_ms"]
        self.last_shot_time = pygame.time.get_ticks()
        self.max_speed = p["max_speed"]
        self.collision_with_enemy_damage = p["collision_with_enemy_damage"]

        self.base_fire_delay = self.fire_delay
        self.base_max_speed = self.max_speed

        self.active_powerups = {}

        self.sprite_key = "player_ship"
        if self.sprite_key in loaded_sprites:
            data = loaded_sprites[self.sprite_key]
            self.sprite_surf = data["surface"]
            self.sprite_offset = data["offset"]
            self.z_order = data["z_order"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)
            self.z_order = 0

    def update(self):
        self.handle_powerup_expiration()
        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.x
        dy = mouse_y - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            if dist > self.max_speed:
                scale = self.max_speed / dist
                dx *= scale
                dy *= scale
            self.x += dx
            self.y += dy

        # Clamp to screen boundaries
        self.x = max(self.radius, min(WIN_WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(WIN_HEIGHT - self.radius, self.y))

    def handle_powerup_expiration(self):
        now = pygame.time.get_ticks()
        expired = [ptype for ptype, end_time in self.active_powerups.items() if now >= end_time]
        for ptype in expired:
            del self.active_powerups[ptype]

        self.fire_delay = self.base_fire_delay
        self.max_speed = self.base_max_speed

        if "rapid_fire" in self.active_powerups:
            factor = config["powerups"]["rapid_fire"]["fire_delay_factor"]
            self.fire_delay = int(self.base_fire_delay * factor)

        if "speed_boost" in self.active_powerups:
            multiplier = config["powerups"]["speed_boost"]["speed_multiplier"]
            self.max_speed = self.base_max_speed * multiplier

    def shoot(self, bullets):
        now = pygame.time.get_ticks()
        if now - self.last_shot_time >= self.fire_delay:
            bullet_conf = config["bullet"]
            # Play shoot SFX if available
            if sound_effects.get("shoot"):
                sound_effects["shoot"].play()

            if "spread_shot" in self.active_powerups:
                sconf = config["powerups"]["spread_shot"]
                count = sconf["bullet_count"]
                angle_deg = sconf["angle_degrees"]
                total_spread = (count - 1) * angle_deg
                start_angle = -total_spread / 2

                for i in range(count):
                    angle = math.radians(start_angle + i * angle_deg)
                    base_speed = -bullet_conf["player_bullet_speed_y"]
                    dx = base_speed * math.sin(angle)
                    dy = base_speed * -math.cos(angle)
                    bullets.append(Bullet(
                        x=self.x,
                        y=self.y,
                        dx=dx,
                        dy=dy,
                        color=tuple(bullet_conf["player_bullet_color"]),
                        from_player=True
                    ))
            else:
                bullet_speed = bullet_conf["player_bullet_speed_y"]
                bullets.append(Bullet(
                    x=self.x,
                    y=self.y,
                    dx=0,
                    dy=bullet_speed,
                    color=tuple(bullet_conf["player_bullet_color"]),
                    from_player=True
                ))
            self.last_shot_time = now

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            draw_x = int(self.x - offset_x)
            draw_y = int(self.y - offset_y)
            screen.blit(self.sprite_surf, (draw_x, draw_y))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def is_shielded(self):
        return "shield" in self.active_powerups

    def apply_powerup(self, ptype, custom_duration):
        now = pygame.time.get_ticks()
        end_time = now + custom_duration
        self.active_powerups[ptype] = end_time


class Bullet:
    def __init__(self, x, y, dx, dy, color, from_player=False):
        b = config["bullet"]
        self.radius = b["radius"]
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = color
        self.from_player = from_player

        if from_player:
            self.sprite_key = "player_bullet"
        else:
            self.sprite_key = "enemy_bullet"

        if self.sprite_key in loaded_sprites:
            data = loaded_sprites[self.sprite_key]
            self.sprite_surf = data["surface"]
            self.sprite_offset = data["offset"]
            self.z_order = data["z_order"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)
            self.z_order = 0

    def update(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
            
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.x < 0 or self.x > WIN_WIDTH or self.y < 0 or self.y > WIN_HEIGHT)


class Enemy:
    def __init__(self, x, y, speed, difficulty):
        e = config["enemy"]
        self.radius = e["radius"]
        self.color = tuple(e["color"])
        self.health = e["initial_health"]
        self.fire_delay = e["fire_delay_ms"]
        self.last_shot_time = pygame.time.get_ticks()

        self.x = x
        self.y = y
        self.speed = speed
        self.difficulty = difficulty

        self.sprite_key = "enemy_ship"
        if self.sprite_key in loaded_sprites:
            data = loaded_sprites[self.sprite_key]
            self.sprite_surf = data["surface"]
            self.sprite_offset = data["offset"]
            self.z_order = data["z_order"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)
            self.z_order = 0

    def update(self, bullets, player):
        self.y += self.speed

        now = pygame.time.get_ticks()
        if now - self.last_shot_time >= self.fire_delay:
            bullet_conf = config["bullet"]
            angle = math.atan2(player.y - self.y, player.x - self.x)
            bullet_speed = bullet_conf["enemy_bullet_base_speed"] + (self.difficulty * 0.1)
            dx = bullet_speed * math.cos(angle)
            dy = bullet_speed * math.sin(angle)
            bullets.append(Bullet(
                x=self.x,
                y=self.y,
                dx=dx,
                dy=dy,
                color=tuple(bullet_conf["enemy_bullet_color"]),
                from_player=False
            ))
            self.last_shot_time = now

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)


class Obstacle:
    def __init__(self):
        o = config["obstacle"]
        self.radius = random.randint(o["radius_min"], o["radius_max"])
        self.color = tuple(o["color"])
        self.health = o["initial_health"]
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(o["speed_min"], o["speed_max"])
        self.collision_damage = o["collision_damage"]

        self.sprite_key = "obstacle"
        info = loaded_sprites.get(self.sprite_key)
        if info:
            base_surf = info["surface"]
            new_width = 2 * self.radius
            new_height = 2 * self.radius
            self.sprite_surf = pygame.transform.scale(base_surf, (new_width, new_height))
            self.sprite_offset = (self.radius, self.radius)
            self.z_order = info["z_order"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)
            self.z_order = 0

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)


class HealthPickup:
    def __init__(self):
        p = config["pickup"]
        self.radius = p["radius"]
        self.color = tuple(p["color"])
        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(p["speed_min"], p["speed_max"])
        self.restore_amount = p["restore_amount"]

        self.sprite_key = "health_pickup"
        if self.sprite_key in loaded_sprites:
            data = loaded_sprites[self.sprite_key]
            self.sprite_surf = data["surface"]
            self.sprite_offset = data["offset"]
            self.z_order = data["z_order"]
        else:
            self.sprite_surf = None
            self.sprite_offset = (self.radius, self.radius)
            self.z_order = 0

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        if self.sprite_surf:
            offset_x, offset_y = self.sprite_offset
            screen.blit(self.sprite_surf, (int(self.x - offset_x), int(self.y - offset_y)))
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        
        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            pygame.draw.circle(screen, (255, 0, 0), (int(self.x), int(self.y)), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)


class Powerup:
    def __init__(self, ptype):
        self.ptype = ptype
        pconf = config["powerups"][ptype]
        self.base_duration = pconf["duration"]
        self.color = tuple(pconf.get("color", [255, 255, 255]))

        self.rarity = self.pick_rarity()
        rar_conf = config["powerups"]["rarities"][self.rarity]
        self.duration = int(self.base_duration * rar_conf["duration_multiplier"])
        self.outline_color = tuple(rar_conf["outline_color"])
        self.outline_thickness = rar_conf["outline_thickness"]

        self.radius = 16

        path = pconf.get("sprite_path", "")
        self.sprite_surf = None
        self.sprite_offset = (self.radius, self.radius)
        if path and os.path.isfile(path):
            surf = pygame.image.load(path).convert_alpha()
            diameter = 2 * self.radius
            self.sprite_surf = pygame.transform.scale(surf, (diameter, diameter))

        self.x = random.randint(self.radius, WIN_WIDTH - self.radius)
        self.y = -self.radius
        self.speed = random.uniform(1.0, 2.0)
        self.z_order = 3

    def pick_rarity(self):
        rarities = config["powerups"]["rarities"]
        c_weight = rarities["common"]["weight"]
        u_weight = rarities["uncommon"]["weight"]
        r_weight = rarities["rare"]["weight"]
        total = c_weight + u_weight + r_weight
        roll = random.random() * total
        if roll < c_weight:
            return "common"
        roll -= c_weight
        if roll < u_weight:
            return "uncommon"
        return "rare"

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        cx = int(self.x)
        cy = int(self.y)

        pygame.draw.circle(
            screen, 
            self.outline_color, 
            (cx, cy), 
            self.radius + self.outline_thickness
        )
        if self.sprite_surf:
            screen.blit(self.sprite_surf, (cx - self.radius, cy - self.radius))
        else:
            pygame.draw.circle(screen, self.color, (cx, cy), self.radius)

        debug_collisions = config.get("debug", {}).get("show_collision_circles", False)
        if debug_collisions:
            pygame.draw.circle(screen, (255, 0, 0), (cx, cy), self.radius, width=1)

    def off_screen(self):
        return (self.y > WIN_HEIGHT + self.radius)

# -----------------------------------------------------------------------------
# MAIN GAME
# -----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Starfield Storm w/ Distinct Sound Effects")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "MENU"
        
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.obstacles = []
        self.pickups = []
        self.powerups = []

        self.score = 0

        diff_conf = config["difficulty"]
        self.wave_interval = diff_conf["wave_interval_start_ms"]
        self.wave_interval_min = diff_conf["wave_interval_min_ms"]
        self.wave_interval_decrement = diff_conf["wave_interval_decrement_ms"]
        self.last_wave_time = pygame.time.get_ticks()

        self.stars = [
            (random.randint(0, WIN_WIDTH), random.randint(0, WIN_HEIGHT))
            for _ in range(100)
        ]

    def run(self):
        while self.running:
            if self.state == "MENU":
                self.menu_loop()
            elif self.state == "GAME":
                self.game_loop()
            elif self.state == "GAME_OVER":
                self.game_over_loop()
        pygame.quit()
        sys.exit()

    def menu_loop(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_text("STARFIELD STORM + Distinct SFX", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 90, COLOR_WHITE)
        self.draw_text("Press [SPACE] to START or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 40, COLOR_WHITE)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.reset_game()
                    self.state = "GAME"

    def game_over_loop(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_text("GAME OVER", 50, WIN_WIDTH // 2, WIN_HEIGHT // 2 - 50, (255, 0, 0))
        self.draw_text(f"FINAL SCORE: {int(self.score)}", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2, COLOR_WHITE)
        self.draw_text("Press [R] to RESTART or [Q] to QUIT", 24, WIN_WIDTH // 2, WIN_HEIGHT // 2 + 50, COLOR_WHITE)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.reset_game()
                    self.state = "GAME"

    def game_loop(self):
        dt = self.clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

        self.update_stars()

        self.player.update()
        self.player.shoot(self.bullets)

        diff_conf = config["difficulty"]
        elapsed_time = pygame.time.get_ticks()
        difficulty = (elapsed_time // diff_conf["time_scale_ms"])
        self.score += 0.03

        # Wave spawn
        if elapsed_time - self.last_wave_time >= self.wave_interval:
            self.spawn_enemies(difficulty)
            self.spawn_obstacles(difficulty)
            self.spawn_health_pickups()
            self.spawn_powerups() 

            self.last_wave_time = elapsed_time
            self.wave_interval = max(self.wave_interval_min, self.wave_interval - self.wave_interval_decrement)

        # Update bullets
        for b in self.bullets[:]:
            b.update()
            if b.off_screen():
                self.bullets.remove(b)

        # Update enemies
        for e in self.enemies[:]:
            e.update(self.bullets, self.player)
            if e.off_screen():
                self.enemies.remove(e)

        # Update obstacles
        for o in self.obstacles[:]:
            o.update()
            if o.off_screen():
                self.obstacles.remove(o)

        # Update pickups
        for p in self.pickups[:]:
            p.update()
            if p.off_screen():
                self.pickups.remove(p)

        # Update powerups
        for pw in self.powerups[:]:
            pw.update()
            if pw.off_screen():
                self.powerups.remove(pw)

        # Collisions
        self.handle_collisions()

        if self.player.health <= 0:
            # Player DIES -> play sfx if available
            if sound_effects.get("player_die"):
                sound_effects["player_die"].play()
            self.state = "GAME_OVER"

        # Draw
        self.draw_game()
        pygame.display.flip()

    def spawn_enemies(self, difficulty):
        diff_conf = config["difficulty"]
        enemy_count = 1 + int(difficulty * diff_conf["enemy_spawn_factor"])
        e_conf = config["enemy"]
        for _ in range(enemy_count):
            x = random.randint(20, WIN_WIDTH - 20)
            y = -30
            speed = e_conf["base_speed"] + difficulty * 0.05
            self.enemies.append(Enemy(x, y, speed, difficulty))

    def spawn_obstacles(self, difficulty):
        diff_conf = config["difficulty"]
        obstacle_count = max(1, int(difficulty // diff_conf["obstacle_spawn_factor"]))
        for _ in range(obstacle_count):
            self.obstacles.append(Obstacle())

    def spawn_health_pickups(self):
        diff_conf = config["difficulty"]
        if random.random() < diff_conf["pickup_chance"]:
            self.pickups.append(HealthPickup())

    def spawn_powerups(self):
        pw_conf = config.get("powerups", {})
        for ptype, info in pw_conf.items():
            if ptype == "rarities":
                continue
            chance = info.get("spawn_chance", 0.0)
            if random.random() < chance:
                self.powerups.append(Powerup(ptype))

    def handle_collisions(self):
        bullet_conf = config["bullet"]
        enemy_bullet_damage = bullet_conf["enemy_bullet_damage"]

        # Player bullets vs. Enemies / Obstacles
        for b in self.bullets[:]:
            if b.from_player:
                # Check enemies
                for e in self.enemies[:]:
                    if self.distance(b.x, b.y, e.x, e.y) < (b.radius + e.radius):
                        e.health -= 1
                        # Enemy hit => play SFX if available
                        if sound_effects.get("enemy_hit"):
                            sound_effects["enemy_hit"].play()

                        if e.health <= 0:
                            # Enemy die => play "enemy_die"
                            if sound_effects.get("enemy_die"):
                                sound_effects["enemy_die"].play()
                            self.enemies.remove(e)
                            self.score += 10
                        if b in self.bullets:
                            self.bullets.remove(b)
                        break
                else:
                    # Check obstacles
                    for o in self.obstacles[:]:
                        if self.distance(b.x, b.y, o.x, o.y) < (b.radius + o.radius):
                            o.health -= 1
                            # Optionally you can have an "obstacle_hit" SFX if you want
                            if o.health <= 0:
                                # We can reuse "enemy_die" or define "obstacle_die"
                                self.obstacles.remove(o)
                                self.score += 10
                            if b in self.bullets:
                                self.bullets.remove(b)
                            break

        # Enemy bullets vs. Player
        for b in self.bullets[:]:
            if not b.from_player:
                if self.distance(b.x, b.y, self.player.x, self.player.y) < (b.radius + self.player.radius):
                    if not self.player.is_shielded():
                        # Player is hit => "player_hit"
                        if sound_effects.get("player_hit"):
                            sound_effects["player_hit"].play()
                        self.player.health -= enemy_bullet_damage
                    if b in self.bullets:
                        self.bullets.remove(b)

        # Obstacles vs. Player
        for o in self.obstacles[:]:
            if self.distance(o.x, o.y, self.player.x, self.player.y) < (o.radius + self.player.radius):
                if not self.player.is_shielded():
                    # Obstacle hits player => "obstacle_hit_player"
                    if sound_effects.get("obstacle_hit_player"):
                        sound_effects["obstacle_hit_player"].play()
                    self.player.health -= o.collision_damage
                if o in self.obstacles:
                    self.obstacles.remove(o)

        # Enemies vs Player (ramming)
        for e in self.enemies[:]:
            if self.distance(e.x, e.y, self.player.x, self.player.y) < (e.radius + self.player.radius):
                if not self.player.is_shielded():
                    # Player is hit => "player_hit"
                    if sound_effects.get("player_hit"):
                        sound_effects["player_hit"].play()
                    self.player.health -= self.player.collision_with_enemy_damage
                if e in self.enemies:
                    # Possibly also kill enemy if you want to (like a suicide run)
                    self.enemies.remove(e)

        # Health pickups vs Player
        for p in self.pickups[:]:
            if self.distance(p.x, p.y, self.player.x, self.player.y) < (p.radius + self.player.radius):
                self.player.health += p.restore_amount
                max_hp = config["player"]["initial_health"]
                self.player.health = min(self.player.health, max_hp)
                self.pickups.remove(p)

        # Powerups vs Player
        for pw in self.powerups[:]:
            if self.distance(pw.x, pw.y, self.player.x, self.player.y) < (pw.radius + self.player.radius):
                ptype = pw.ptype
                self.player.apply_powerup(ptype, pw.duration)

                # Distinct SFX for each powerup type
                # We'll build a key like "powerup_" + ptype
                sfx_key = f"powerup_{ptype}"
                if sound_effects.get(sfx_key):
                    sound_effects[sfx_key].play()

                if ptype == "nuke":
                    # nuke => kill all enemies & obstacles
                    for e in self.enemies:
                        if sound_effects.get("enemy_die"):
                            sound_effects["enemy_die"].play()
                        self.score += 10
                    for o in self.obstacles:
                        self.score += 10
                    self.enemies.clear()
                    self.obstacles.clear()

                self.powerups.remove(pw)

    def distance(self, x1, y1, x2, y2):
        return math.hypot(x2 - x1, y2 - y1)

    def update_stars(self):
        new_stars = []
        for (sx, sy) in self.stars:
            sy += 2
            if sy > WIN_HEIGHT:
                sy = 0
                sx = random.randint(0, WIN_WIDTH)
            new_stars.append((sx, sy))
        self.stars = new_stars

    def draw_game(self):
        self.screen.fill(COLOR_BLACK)

        # Draw starfield
        for (sx, sy) in self.stars:
            pygame.draw.circle(self.screen, COLOR_WHITE, (sx, sy), 2)

        # Collect all objects in a list for z_order sorting
        to_draw = []
        to_draw.append((self.player.z_order, self.player))
        for b in self.bullets:
            to_draw.append((b.z_order, b))
        for e in self.enemies:
            to_draw.append((e.z_order, e))
        for o in self.obstacles:
            to_draw.append((o.z_order, o))
        for p in self.pickups:
            to_draw.append((p.z_order, p))
        for pw in self.powerups:
            to_draw.append((pw.z_order, pw))

        to_draw.sort(key=lambda x: x[0])
        for (_, obj) in to_draw:
            obj.draw(self.screen)

        # UI
        self.draw_text(f"Score: {int(self.score)}", 24, 50, 20, COLOR_WHITE, align="left")
        self.draw_text(f"Health: {self.player.health}", 24, WIN_WIDTH - 150, 20, COLOR_WHITE, align="left")

    def draw_text(self, text, size, x, y, color, align="center"):
        font = pygame.font.SysFont(None, size)
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if align == "center":
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)

    def reset_game(self):
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.obstacles = []
        self.pickups = []
        self.powerups = []
        self.score = 0

        diff_conf = config["difficulty"]
        self.wave_interval = diff_conf["wave_interval_start_ms"]
        self.wave_interval_min = diff_conf["wave_interval_min_ms"]
        self.wave_interval_decrement = diff_conf["wave_interval_decrement_ms"]
        self.last_wave_time = pygame.time.get_ticks()

        self.stars = [
            (random.randint(0, WIN_WIDTH), random.randint(0, WIN_HEIGHT))
            for _ in range(100)
        ]

    def draw_text(self, text, size, x, y, color, align="center"):
        font = pygame.font.SysFont(None, size)
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if align == "center":
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)

def main():
    game = Game()
    game.run()

if __name__ == "__main__":
    main()

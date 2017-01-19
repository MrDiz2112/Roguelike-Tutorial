import libtcodpy as libtcod

import math
import textwrap

# Screen settings
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# Map settings
MAP_WIDTH = 80
MAP_HEIGHT = 43

# Sizes and coordinates relevant for the GUI

# Bar constants
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
INVENTORY_WIDTH = 50

# Message bar constants
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

# Parameters for dungeon generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

# Parameters for FOV
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)

LIMIT_FPS = 60

HEAL_AMOUNT = 4

LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

##############################################################################
# Basic Classes
##############################################################################


class Tile:
    # a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked

        # by default, if a tile is blocked, it also blocks sight
        if block_sight is None:
            block_sight = blocked

        self.block_sight = block_sight

        self.explored = False


class Rect:
    # a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        # returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


class Object:
    # this is a generic object: the player, a monster, an item, the stairs...
    def __init__(self, x, y, char, name, color, blocks=False, fighter = None, ai = None, item=None):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks

        self.fighter = fighter
        if self.fighter: # Let the fighter component know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

    def move(self, dx, dy):
        # move by the given amount
        if not isBlocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        # Vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Normalize it to length 1 (preserving direction), then round it
        # and convert to integer
        dx = int(round(dx/distance))
        dy = int(round(dy/distance))
        self.move(dx, dy)

    def move_astar(self, target):
        # Create a FOV map that has the dimensions of the map
        fov = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)

        # Scan the current map each turn and set all the wall unwalkable
        for y1 in range(MAP_HEIGHT):
            for x1 in range(MAP_WIDTH):
                libtcod.map_set_properties(fov, x1, y1, not map[x1][y1].block_sight,
                                           not map[x1][y1].blocked)

        # Scan all the objects to see if there are objects that must be navigated around
        # Check also that the object isn't self or the target (so that the start and the end points are free)
        # The AI class handles the situation if self is next to the target so it will not use this A* function anyway
        for obj in objects:
            if obj.blocks and obj != self and obj != target:
                # Set the tile as a wall so it must be navigated around
                libtcod.map_set_properties(fov, obj.x, obj.y, True, False)

        # Allocate a A* path
        # The 1.41 is the normal diagonal cost of moving (sqrt(2)).
        my_path = libtcod.path_new_using_map(fov, 1.41)

        # Compute the path between self's coordinates and the target's coordinates
        libtcod.path_compute(my_path, self.x, self.y, target.x, target.y)

        # Check if the path exists, and in this case, also the path is shorter than 25 tiles
        #
        # The path size matters if you want the monster to use alternative longer paths (for example through other
        # rooms) if for example the player is in a corridor
        #
        # It makes sense to keep path size relatively low to keep the monsters from running around the map if
        # there's an alternative path really far away
        if not libtcod.path_is_empty(my_path) and libtcod.path_size(my_path) < 25:
            # Find the next coordinates in the computed full path
            x, y = libtcod.path_walk(my_path, True)
            if x or y:
                # Set self's coordinates to the next path tile
                self.x = x
                self.y = y
        else:
            # Keep the old move function as a backup so that if there are no paths (for example another
            # monster blocks a corridor) it will still try to move towards the player (closer to the
            # corridor opening)
            self.move_towards(target.x, target.y)

        # Delete the path to free memory
        libtcod.path_delete(my_path)


    def distance_to(self, other):
        # Return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        # Return distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)


    def draw(self):
        # only show if it's visible to the player
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
            # set the color and then draw the character that represents this object at its position
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def send_to_back(self):
        # make this object be drawn first, so all others
        # appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)

##############################################################################
# Components
##############################################################################


class Fighter:
    # Combat-related properties and methods (monster, player, NPC)
    def __init__(self, hp, defence, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defence = defence
        self.power = power

        self.death_function = death_function

    def take_damage(self, damage):
        # Apply damage if possible
        if damage > 0:
            self.hp -= damage

            # check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

    def attack(self, target):
        # a simple formula for attack damage
        damage = self.power - target.fighter.defence

        if damage > 0:
            # make the target take some damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' HP.',
                    libtcod.white)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!',
                    libtcod.white)

    def heal(self, amount):
        # Heal by given amount, without going over maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp


class BasicMonster:
    # AI for basic monster
    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

            # Move toward player if far away
            if monster.distance_to(player) >= 2:
                monster.move_astar(player)

            # Close enough, attack! (if player is still alive)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class ConfusedMonster:
    # AI for a temporarily confused monster (reverts to previous AI after a while)
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0: # still confused...
            # Move to the random direction
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        else: # restore previous AI (this one will be deleted because it's not referenced anymore)
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + 'is no longer confused!', libtcod.red)


class Item:
    # an item can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function

    def pick_up(self):
        # add to the player inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full! Cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)

    def use(self):
        # Call the "use_function if it's defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used!')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) # destroy after use, unless it was cancelled for some reason

    def drop(self):
        # add to the map and remove from the player's inventory. also, place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You droppend a ' + self.owner.name + '.', libtcod.yellow)

##############################################################################
# Functions
##############################################################################


# Build rooms


def create_room(room):
    global map
    # go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False


def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def create_v_tunnel(y1, y2, x):
    global map
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


# Game functions


def player_move_or_attack(dx, dy):
    global fov_recompute

    # the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    # try to find an attackable object here
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    # attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True


def handle_keys():
    global key

    # Alt+Enter: toggle fullscreen
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    # Esc: exit game
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'  # Exit game

    # Movement keys
    if game_state == 'playing':
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)

        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)

        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)

        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)

        # Diagonal movement
        # Down-left
        elif key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)

        # Down-right
        elif key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)

        # Up-left
        elif key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)

        # Up-right
        elif key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)

        else:
            # test for other keys
            key_char = chr(key.c)

            if key_char == 'g':
                #pick up an item
                for object in objects: #look for an item in the player's tile
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break

            if key_char == 'i':
                # Show the inventory; if an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()

            if key_char == 'd':
                # show the inventory; if an item selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            return 'didnt-take-turn'


def get_names_under_mouse():
    global mouse

    # return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)

    # create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.name for obj in objects
             if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ', '.join(names) #join the names, separated by commas
    return names.capitalize()


def inventory_menu(header):
    # Show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    # if an item was chosen, return it
    if index is None or len(inventory) == 0:
        return None

    return inventory[index].item


def closest_monster(max_range):
    # Find closest enemy, up to the maximum range, and in player FOV
    closest_enemy = None
    closest_dist = max_range + 1 #start with (slightly more then) maximum range

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            # Calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist: # it's closer, so remember it
                closest_enemy = object
                closest_dist = dist

    return closest_enemy


def target_tile(max_range=None):
    # return the position of a tile left-clicked in player's FOV
    # (optionally in a range), or (None,None) if right-clicked.
    global key, mouse
    while True:
        # render the screen. this erases the inventory and shows the names
        # of objects under the mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        (x, y) = (mouse.cx, mouse.cy)

        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None) # cancel if the player right-clicked or pressed Escape

        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
                (max_range is None or player.distance(x, y) <= max_range)):
            return (x, y)


def target_monster(max_range=None):
    # returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None: # player cancelled
            return None

    #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj


# Item components


def cast_heal():
    # Heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health!', libtcod.light_red)
        return 'cancelled'

    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)


def cast_lightning():
    # Find the closest enemy (inside a maximum range) and damage it
    monster = closest_monster(LIGHTNING_RANGE)

    if monster is None: # no enemy found within maximum range
        message('No enemy is close enough to strike', libtcod.red)
        return 'cancelled'

    # Zap it!
    message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! The damage is '
            + str(LIGHTNING_DAMAGE) + ' HP.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)


def cast_confuse():
    # Ask the player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None:
        return 'cancelled'

    # Replace the monster's AI with a "confused" one; after some turns it will restore the old AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster # Tells the new component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)


def cast_fireball():
    # ask player for a target tile to throw fireball at
    message('Left-click a target tile for the fireball or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None:
        return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!',
            libtcod.orange)

    for obj in objects: # damage every fighter in range, including player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' HP.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)


# Death functions


def player_death(player):
    # The game is ended
    global  game_state
    message('You died!', libtcod.red)
    game_state = 'dead'

    # transform player into a corpse
    player.char = '%'
    player.color = libtcod.dark_red


def monster_death(monster):
    # transform it into a nasty corpse! it doesn't block, can't be
    # attacked and doesn't move
    message(monster.name.capitalize() + ' is dead!', libtcod.yellow)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()


# Objects functions


def isBlocked(x, y):
    # Test the map tiles
    if map[x][y].blocked:
        return True

    # Check for the blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False


def place_objects(room):
    # choose random numbers of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        # choose a random spot for monster
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not isBlocked(x, y):
            if libtcod.random_get_int(0, 0, 100) < 80: # 80% chance of getting an orc
                # create an orc
                fighter_component = Fighter(hp=10, defence=0, power=3,
                                            death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks=True,
                                 fighter=fighter_component, ai=ai_component)
            else:
                # create a troll
                fighter_component = Fighter(hp=16, defence=1, power=4,
                                            death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'T', 'troll', libtcod.black, blocks=True,
                                 fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    # choose random number of items
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        # choose random spot for the items
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        # only place it if the tile is not blocked
        if not isBlocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)

            if dice < 70:
                # create a healing potion (70% chance)
                item_component = Item(use_function=cast_heal)

                item = Object(x, y, '!', 'healing potion', libtcod.red, item=item_component)
            elif dice < 70 + 10:
                # create a lighting bolt scroll (15% chance)
                item_component = Item(use_function=cast_lightning)

                item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.light_blue, item=item_component)
            elif dice < 70 + 10 +10:
                # create fireball scroll (10% chance)
                item_component = Item(use_function=cast_fireball)

                item = Object(x, y, '#', 'scroll of fireball', libtcod.red, item=item_component)
            else:
                # create a confuse scroll (15% chance)
                item_component = Item(use_function=cast_confuse)

                item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)

            objects.append(item)
            item.send_to_back()



# Map functions


def make_map():
    global map

    # fill map with "blocked" tiles
    map = [[Tile(True) for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH)]

    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        # Random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # Random position without going out of the boundaries of the map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT -h - 1)

        # "Rect" class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)

        # run through the other rooms and see if they intersect with this one
        failed = False
        for other_rooms in rooms:
            if new_room.intersect(other_rooms):
                failed = True
                break

        if not failed:
            # This means there are no intersections, so this room is valid

            # paint" it to the map's tiles
            create_room(new_room)

            # Center coordinates of new room
            (new_x, new_y) = new_room.center()

            if num_rooms == 0:
                # This is the first room, where the player starts at
                player.x = new_x
                player.y = new_y
            else:
                # All rooms after the first:
                # connect it to the previous room with a tunnel

                # center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms -1].center()

                # Draw a tunel (random number that is either 0 or 1)
                if libtcod.random_get_int(0, 0, 1) == 1:
                    # First move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    # First move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            #add some contents to this room
            place_objects(new_room)

            rooms.append(new_room)
            num_rooms += 1


# Render functions


def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    # Render a bar (HP, experience, etc)

    # First calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)

    # Render the background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

    # Render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

    # Render the centered text with the values
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
                             name + ' : ' + str(value) + '/' + str(maximum))


def message(new_msg, color=libtcod.white):
    # Split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        # if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        # add the new line as a tuple, with the text and the color
        game_msgs.append((line, color))


def menu(header, options, width):
    if len(options) > 26:
        raise ValueError('Cannot have a menu with more then 26 options.')

    # Calculate a total height for the header (after auto-wrap) and one lien per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    height = len(options) + header_height

    # Create a new off-screen console represents the menu's window
    window = libtcod.console_new(width, height)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE,
                                  libtcod.LEFT, header)
    libtcod.console_set_default_background(window, libtcod.blue)
    libtcod.console_rect(window, 0, 0, width, header_height - 1, False, libtcod.BKGND_SET)

    # Print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    # Blit the content of the "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    # Present the root console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    # Convert the ASCII code and index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options):
        return index

    return None


def render_all():
    global fov_map
    global color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

    if fov_recompute:
        # recompute FOV if needed
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

    # go through all tiles, and set their background color according to the FOV
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            visible = libtcod.map_is_in_fov(fov_map, x, y)
            wall = map[x][y].block_sight
            if not visible:
                # if it's not visible right now, the player can only see it if it's explored
                if map[x][y].explored:
                    # it's out of the player's FOV
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
            else:
                if wall:
                    libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                else:
                    libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                map[x][y].explored = True

    # draw all objects in the objects list
    for object in objects:
        if object != player:
            object.draw()
    player.draw()

    # Blit the contents of "con" to the root console
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

    # Prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    # Print the game message, one line at time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1

    # Show the player stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
               libtcod.red, libtcod.dark_red)

    # display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    # Blit the contents of 'panel' to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)


######################################################################################
# Initialization
######################################################################################

# Set up the game

libtcod.console_set_custom_font('terminal8x8_gs_ro.png', libtcod.FONT_TYPE_GRAYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'My first Roguelike', False)
libtcod.sys_set_fps(LIMIT_FPS)

# New off-screen console
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)

# Console for GUI panel
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

# Create Player Object
fighter_component = Fighter(hp=30, defence=2, power=5,
                            death_function=player_death)

player = Object(0, 0, libtcod.CHAR_SMILIE, 'player', libtcod.white, blocks=True,
                fighter=fighter_component)

# List of objects
objects = [player]

# generate map (at this point it's not drawn to the screen)
make_map()

# create the FOV map, according to the generated map
fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

# Game variables
game_state = 'playing'
player_action = None
fov_recompute = True

inventory = []

# Create the list of game messages and their colors, starts empty
game_msgs = []

# a warm welcoming message!
message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', libtcod.red)

mouse = libtcod.Mouse()
key = libtcod.Key()


######################################################################################
# Main loop
######################################################################################

while not libtcod.console_is_window_closed():
    # render the screen
    libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
    render_all()

    libtcod.console_flush()

    # Erase all objects at their old locations, before they move
    for object in objects:
        object.clear()

    # Handle keys and exit game if needed
    player_action = handle_keys()
    if player_action == 'exit':
        break

    # Monsters take their turns
    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for object in objects:
            if object.ai:
                object.ai.take_turn()
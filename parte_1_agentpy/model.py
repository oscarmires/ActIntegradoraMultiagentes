
# Model design
import random
import time

import agentpy as ap

# Visualization
import matplotlib.pyplot as plt
import matplotlib.animation
import IPython

# Server
import client

# Constants
## Colors
BLUE = 0
GREEN = 1
YELLOW = 2
RED = 3
## Color strings
COLOR_STRINGS = ['BLUE', 'GREEN', 'YELLOW', 'RED']
## Types
TRAFFIC_LIGHT = 0
CAR = 1
## Streets
NO_STREET = 0
HORIZONTAL = 1
VERTICAL = 2


class PositionHandler:

    def __init__(self, grid_size):
        self.grid_size = grid_size
        half = grid_size // 2

        self.spawn_points = [
            {'coord': (0, half - 1), 'dir': (1, 0)},                # UP
            {'coord': (half - 1, grid_size - 1), 'dir': (0, -1)},   # RIGHT
            {'coord': (grid_size - 1, half), 'dir': (-1, 0)},       # DOWN
            {'coord': (half, 0), 'dir': (0, 1)}                     # LEFT
        ]

        self.traffic_light_positions_h = [
            (half - 1, half),
            (half, half - 1)
        ]

        self.traffic_light_positions_v = [
            (half - 1, half - 1),
            (half, half)
        ]

    def random_spawn_point(self):
        return random.choice(self.spawn_points)

    def get_traffic_light_positions(self):
        return self.traffic_light_positions

    def is_next_position_valid(self, current_pos, dir):
        valid = True
        next_y = current_pos[0] + dir[0]
        next_x = current_pos[1] + dir[1]
        invalid = [-1, self.grid_size]

        if next_y in invalid or next_x in invalid:
            valid = False

        return valid

    def get_traffic_light_orientation(self, pos):
        if pos in self.traffic_light_positions_h:
            return HORIZONTAL
        if pos in self.traffic_light_positions_v:
            return VERTICAL

    def get_car_orientation(self, dir):
        horizontal = [(0, -1), (0, 1)]
        vertical = [(-1, 0), (1, 0)]
        if dir in horizontal:
            return HORIZONTAL
        if dir in vertical:
            return VERTICAL

    def assign_tf_tags(self, traffic_lights, positions):
        half = self.grid_size // 2

        tags = {
            (half - 1, half): 'h1',
            (half, half - 1): 'h2',
            (half - 1, half - 1): 'v1',
            (half, half): 'v2'
        }

        for tf in traffic_lights:
            tf.tag = tags[positions[tf]]

class Car(ap.Agent):

    def setup(self):
        self.color = BLUE
        self.type = CAR
        self.direction = (0, 0)

    def get_dir(self):
        return self.direction

    def get_next_pos(self, current_pos):
        return current_pos[0] + self.direction[0], current_pos[1] + self.direction[1]


class TrafficLight(ap.Agent):

    def setup(self):
        self.color = YELLOW
        self.type = TRAFFIC_LIGHT


class StreetModel(ap.Model):

    def setup(self):
        # Server
        self.client = client.Client()

        # Position handler
        self.ph = PositionHandler(self.p.size)

        # Traffic lights
        self.traffic_lights_h = ap.AgentList(self, 2, TrafficLight)
        self.traffic_lights_v = ap.AgentList(self, 2, TrafficLight)
        self.streets = [None, self.traffic_lights_h, self.traffic_lights_v]

        # Grid
        self.grid = ap.Grid(self, (self.p.size, self.p.size), track_empty=True)
        self.grid.add_agents(self.traffic_lights_h, self.ph.traffic_light_positions_h)
        self.grid.add_agents(self.traffic_lights_v, self.ph.traffic_light_positions_v)
        self.ph.assign_tf_tags(self.traffic_lights_h, self.grid.positions)
        self.ph.assign_tf_tags(self.traffic_lights_v, self.grid.positions)

        # Counters
        self.car_count = 0

        # Flags
        self.stopped_street = NO_STREET
        self.green_light_countdown = 0

    def step(self):
        time.sleep(self.p.step_dur)

        if self.car_count < self.p.n_cars:
            self.add_car()

        self.run_traffic_lights_program()
        self.move_cars()

        # Update database
        data = {
            'cars': [],
            'trafficLights': []
        }

        for agent in self.grid.agents:
            position = self.grid.positions[agent]
            if agent.type == CAR:
                car = {
                    'id': agent.id,
                    'x': position[1],
                    'y': position[0],
                    'z': 0
                }
                data['cars'].append(car)
            elif agent.type == TRAFFIC_LIGHT:
                traffic_light = {
                    'id': agent.id,
                    'color': COLOR_STRINGS[agent.color],
                    'tag': agent.tag
                }
                data['trafficLights'].append(traffic_light)

        self.client.set_data(data)
        self.client.commit()

        if self.t == self.p.steps:
            self.stop()

    def end(self):
        self.client.delete()

    def add_car(self):
        spawn_point = self.ph.random_spawn_point()
        new_car = ap.AgentList(self, 1, Car)
        new_car.direction = spawn_point['dir']
        self.grid.add_agents(new_car, [spawn_point['coord']])
        self.car_count += 1

    def remove_car(self, car):
        self.grid.remove_agents(car)

    def restart_green_light_countdown(self):
        self.green_light_countdown = self.p.traffic_light_dur

    def neighbor_cars_present(self, street):
        traffic_lights = self.streets[street]

        for agent in traffic_lights:
            for neighbor in self.grid.neighbors(agent):
                if neighbor.type == CAR:
                    car_next_pos = neighbor.get_next_pos(self.grid.positions[neighbor])
                    traffic_light_pos = self.grid.positions[agent]
                    return car_next_pos == traffic_light_pos
        return False

    def activate_green_light(self, street):
        other_street = VERTICAL
        if street == VERTICAL:
            other_street = HORIZONTAL
        elif street == HORIZONTAL:
            other_street = VERTICAL
        self.streets[street].color = GREEN
        self.streets[other_street].color = RED
        self.stopped_street = other_street

    def activate_yellow_light(self):
        self.traffic_lights_h.color = YELLOW
        self.traffic_lights_v.color = YELLOW
        self.stopped_street = NO_STREET

    def run_traffic_lights_program(self):
        if self.stopped_street == NO_STREET:
            # all lights are yellow at this moment
            if self.neighbor_cars_present(HORIZONTAL):
                self.activate_green_light(HORIZONTAL)
            if self.neighbor_cars_present(VERTICAL):
                self.activate_green_light(VERTICAL)
            self.restart_green_light_countdown()
        else:
            # lights are not yellow at this moment
            if self.green_light_countdown == 0:
                if self.neighbor_cars_present(self.stopped_street):
                    self.activate_green_light(self.stopped_street)
                    self.restart_green_light_countdown()
                else:
                    self.activate_yellow_light()
            else:
                self.green_light_countdown -= 1

    def neighbor_traffic_light(self, car):
        # TODO remove
        positions = self.grid.positions
        for neighbor in self.grid.neighbors(car):
            next_pos = car.get_next_pos(positions[car])
            if neighbor.type == TRAFFIC_LIGHT and positions[neighbor] == next_pos:
                return neighbor
        return None

    def neighbors_ahead(self, car):
        positions = self.grid.positions
        next_pos = car.get_next_pos(positions[car])
        neighbors = []
        for neighbor in self.grid.neighbors(car):
            if positions[neighbor] == next_pos:
                neighbors.append(neighbor)
        return neighbors

    def move_cars(self):
        for agent in list(self.grid.agents):
            if agent.type == CAR:

                # delete car if reaches end
                if not self.ph.is_next_position_valid(self.grid.positions[agent], agent.get_dir()):
                    self.grid.remove_agents(agent)
                    continue

                move = True

                neighbors_ahead = self.neighbors_ahead(agent)
                for neighbor in neighbors_ahead:
                    if neighbor.type == TRAFFIC_LIGHT:
                        car_orientation = self.ph.get_car_orientation(agent.get_dir())
                        traffic_light_orientation = self.ph.get_traffic_light_orientation(self.grid.positions[neighbor])
                        same_orientation = car_orientation == traffic_light_orientation
                        if neighbor.color == RED and same_orientation:
                            move = False
                    elif neighbor.type == CAR:
                        move = False

                if random.random() < 0.2:
                    move = False

                if move:
                    self.grid.move_by(agent, agent.get_dir())


parameters = {
    'size': 20,
    'n_cars': 15,
    'steps': 50,
    'step_dur': 0.5,
    'traffic_light_dur': 5
}

model = StreetModel(parameters)
model.run()

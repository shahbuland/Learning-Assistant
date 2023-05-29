from typing import Iterable, Tuple, Dict, Callable
from dataclasses import dataclass

import pygame
import random
import math
import os
import joblib

import tkinter as tk
from tkinter import filedialog

from LearnAssist.chat_harness import BaseChatHarness

@dataclass
class Point:
    x : int
    y : int

    def astuple(self):
        return (self.x, self.y)

    def dist(self, other : 'Point'):
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def translate(self, other : 'Point'):
        return Point(self.x - other.x, self.y - other.y)
    
    def __add__(self, other : 'Point'):
        return Point(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other : 'Point'):
        return self.translate(other)

@dataclass
class Node:
    id : int
    forward_neighbors : Iterable[int]
    backward_neighbors : Iterable[int]
    display_text : str

class SquareButton:
    def __init__(self, pos : Point, size : int, text : str, on_click : Callable, is_toggle : bool = False):
        self.pos = pos
        self.size = size
        self.on = False
        self.text = text
        self.on_click = on_click
        self.is_toggle = is_toggle
    
    def scan(self, mouse_pos : Point):
        """
        Check if mouse is in button boundaries
        """
        if (mouse_pos.x > self.pos.x and mouse_pos.x < (self.pos.x + self.size)) \
            and (mouse_pos.y > self.pos.y and mouse_pos.y < (self.pos.y + self.size)):
            print("Pressed")
            return True
        return False
    
    def draw(self, screen, font):
        button_rect = pygame.Rect(self.pos.x, self.pos.y, self.size, self.size)
        pygame.draw.rect(screen, (0, 0, 0), button_rect)
        if self.on:
            pygame.draw.rect(screen, (0, 255, 0), button_rect, 2)
        else:
            pygame.draw.rect(screen, (255, 255, 255), button_rect, 2)
        
        text_surface = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(self.pos + Point(self.size // 2, self.size // 2)).astuple())   

        screen.blit(text_surface, button_rect)
    
    def toggle(self):
        """
        Button will change color to indicate it is being pressed
        """
        if self.is_toggle:
            self.on = not self.on
    
    def click(self):
        self.toggle()
        self.on_click()

class DirectedGraph:
    def __init__(self):
        self.V : Dict[int, Node] = {}
        self.E : Iterable[Tuple[int,int]] = []

        # Tagged vertices representing things the student already knows
        self.tagged_vertices : Dict[int, bool] = {}

    def add_node(self, id : int, text : str, forward_neighbors : Iterable[int] = [], backward_neighbors : Iterable[int] = []):
        assert (id not in self.V), "Cannot add node with already existing ID"

        self.V[id] = Node(
            id = id,
            forward_neighbors=forward_neighbors,
            backward_neighbors=backward_neighbors,
            display_text=text
        )

        self.tagged_vertices[id] = False # Start off assuming its false

        self.E += [(id, id_f) for id_f in forward_neighbors] + [(id_b, id) for id_b in backward_neighbors]

    def add_edge(self, id_start : int, id_end : int):
        self.E.append((id_start, id_end))
        self.V[id_start].forward_neighbors.append(id_end)
        self.V[id_end].backward_neighbors.append(id_start)

    def __str__(self) -> str:
        s = ""
        for key in self.V:
            s += f"{self.V[key].display_text} ({self.V[key].id} is connected to: "
            for nbr_id in self.V[key].forward_neighbors:
                s += f"{self.V[nbr_id].display_text} ({self.V[nbr_id].id}), "
            s += "\n"
        
        return s
    
    def get_tagged_node_names(self) -> str:
        s = ""
        for key in self.tagged_vertices:
            if self.tagged_vertices[key]:
                s += self.V[key].display_text + ", "

    def from_builder_file(self, path : str):
        with open(path, 'r') as f:
            lines = f.readlines()
        
        def command_arg_split(line):
            command = line.split(" ")[0][1:]
            args = " ".join(line.split(" ")[1:]).split(",")
            args = [arg.strip() for arg in args]
            return command, args

        map_name_id = {}
        for line in lines:
            cmd, args = command_arg_split(line)
            if cmd == "addnode":
                new_id = (max(self.V.keys()) + 1) if self.V else 0
                map_name_id[args[0]] = new_id
                self.add_node(new_id, args[0])

            elif cmd == "addedge":
                node_1 = map_name_id[args[0]]
                node_2 = map_name_id[args[1]]

                self.add_edge(node_1, node_2)

class ChatLog:
    def __init__(self, font, max_messages=10):
        self.font = font
        self.max_messages = max_messages
        self.messages = []
        self.colors = []

    def log(self, message, color):
        self.messages.append(message)
        self.colors.append(color)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
            self.colors.pop(0)

    def draw(self, screen, x, y):
        for i, (message, color) in enumerate(reversed(list(zip(self.messages, self.colors)))):
            message_surface = self.font.render(message, True, color)
            screen.blit(message_surface, (x, y - i * self.font.get_height()))

class GraphExplorer:
    FONT_SIZE = 30
    NODE_SIZE = 60
    EDGE_THICKNESS = 2
    ARROW_LENGTH = 50
    ARROW_THICKNESS = 10
    BUTTON_SIZE  = 100

    def __init__(self, graph: DirectedGraph = None, resolution : Tuple[int,int] = (1900, 1000)):
        if graph is None:
            self.graph = DirectedGraph()
        else:
            self.graph = graph

        pygame.init()

        self.width = resolution[0]
        self.height = resolution[1]

        if not os.path.isdir("./saves"):
            os.path.mkdirs("./saves")

        self.screen = pygame.display.set_mode((resolution[0], resolution[1]))
        self.font = pygame.font.Font(None, self.FONT_SIZE)
        self.running = True

        self.node_centers : Dict[int,Tuple[int,Point]] = {}
        self.initialize_node_centers()

        button_x = self.width - self.BUTTON_SIZE
        button_y = lambda i: (self.height - ((self.BUTTON_SIZE + 2) * i))

        def make_btn(y, txt, clk : Callable, **kwargs):
            return SquareButton(Point(button_x, y), self.BUTTON_SIZE, txt, clk, **kwargs)

        self.buttons : Dict[str, SquareButton] = {
            "move_mode" : make_btn(button_y(1), "Move", self.on_click_move_mode, is_toggle = True),
            "save_button" : make_btn(button_y(2), "Save", self.on_click_save),
            "load_button" : make_btn(button_y(3), "Load", self.on_click_load),
            "tag_vertex" : make_btn(button_y(4), "Mark Learned", self.on_click_tag),
            "from_file" : make_btn(button_y(5), "From File", self.on_click_file)
        }

        # Window controls
        self.screen_offset = Point(0, 0)

        # Trackers
        self.selected_node : int = None
        self.dragging_start_pos : Point = None
        self.dragging_screen_start : Point = None

        # Modes
        self.move_mode : bool = False # Moving node
        self.dragging_mode : bool = False # Moving screen

        # Chatbots
        self.chat_log = ChatLog(self.font, 60)
        self.active_chatbot = "BaseChat"
        self.chat_stack = [self.active_chatbot]

        self.chatbots = { # ChatHarness with names
            "BaseChat" : BaseChatHarness("LearnAssist/prompts/basechat.txt"),
            "Tutor" : BaseChatHarness("LearnAssist/prompts/tutor.txt")
        }
        self.chat_colors = { # names and associated colors
            "User" : (255, 255, 255),
            "BaseChat" : (0, 255, 0),
            "System" : (127, 127, 127),
            "Tutor" : (0, 127, 127)
        }

    # ==== BUTTONS ====
    def check_button_clicks(self, mouse_pos : Point):
        for key in self.buttons:
            if self.buttons[key].scan(mouse_pos):
                return key

    def on_click_move_mode(self):
        self.move_mode = not self.move_mode

    def on_click_save(self):
        self.data = {
            "graph" : self.graph,
            "node_pos" : self.node_centers
        }

        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".graph",
            filetypes=[("Graph files", "*.graph")],
            initialdir="./saves"
        )

        if file_path:
            joblib.dump(self.data, file_path)

    def on_click_load(self):
        # Open a file dialog to select the load path
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        file_path = filedialog.askopenfilename(
            defaultextension=".graph",
            filetypes=[("Graph files", "*.graph")],
            initialdir="./saves"
        )

        if file_path:
            self.data = joblib.load(file_path)
            self.graph = self.data["graph"]
            self.node_centers = self.data["node_pos"]

    def on_click_tag(self):
        id = self.selected_node

        if id == -1:
            return
        
        self.graph.tagged_vertices[id] = not self.graph.tagged_vertices[id]

    def on_click_file(self):
        # Open a file dialog to select the load path
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        file_path = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialdir="./saves/graph_builder"
        )

        if file_path:
            self.graph.from_builder_file(file_path)

        self.initialize_node_centers()

    # ==== BASE GAME FUNCTIONS ====
    def initialize_node_centers(self):
        """
        Initializes nodes starting positions
        """
        min_x, max_x = -500, 1000
        min_y, max_y = -500, 1000
        spacing = 90

        for node_id in self.graph.V:
            while True:
                x = random.randint(min_x, max_x)
                y = random.randint(min_y, max_y)
                if not any(abs(x - point.x) < spacing and abs(y - point.y) < spacing for point in self.node_centers.values()):
                    self.node_centers[node_id] = Point(x, y)
                    break

    def draw_arrow(self, start: Point, end: Point):
        """
        Draw a directed arrow from start to end
        """
        start = start.translate(self.screen_offset)
        end = end.translate(self.screen_offset)

        pygame.draw.line(self.screen, (255, 255, 255), start.astuple(), end.astuple(), self.EDGE_THICKNESS)
        pygame.draw.line(self.screen, (255, 255, 255), start.astuple(), end.astuple(), self.EDGE_THICKNESS)

        # Calculate the angle of the line
        angle = math.atan2(end.y - start.y, end.x - start.x)

        # Arrowhead size
        arrowhead_length = self.ARROW_LENGTH
        arrowhead_angle = math.pi / 6

        midpoint = Point((start.x + end.x) / 2, (start.y + end.y) / 2)

        # Calculate the positions of the two arrowhead lines
        arrowhead_end1 = Point(
            midpoint.x - arrowhead_length * math.cos(angle + arrowhead_angle),
            midpoint.y - arrowhead_length * math.sin(angle + arrowhead_angle)
        )
        arrowhead_end2 = Point(
            midpoint.x - arrowhead_length * math.cos(angle - arrowhead_angle),
            midpoint.y - arrowhead_length * math.sin(angle - arrowhead_angle),
        )

        # Draw the arrowhead lines
        pygame.draw.line(self.screen, (255, 255, 255), midpoint.astuple(), arrowhead_end1.astuple(), self.ARROW_THICKNESS)
        pygame.draw.line(self.screen, (255, 255, 255), midpoint.astuple(), arrowhead_end2.astuple(), self.ARROW_THICKNESS)

    def draw_node(self, pos: Point, text: str, id : int):
        """
        Draw a node given its position, text on it, and its id
        """
        pos = pos.translate(self.screen_offset)

        # Blue halo if it's selected 
        if self.selected_node == id: 
            pygame.draw.circle(self.screen, (0, 0, 255), pos.astuple(), self.NODE_SIZE + 5)
        
        # Green halo if it's learned concept
        if self.graph.tagged_vertices[id]:
            pygame.draw.circle(self.screen, (0, 255, 0), pos.astuple(), self.NODE_SIZE + 2)

        pygame.draw.circle(self.screen, (255, 255, 255), pos.astuple(), self.NODE_SIZE)

        text_surface = self.font.render(text, True, (0, 0, 0))
        text_rect = text_surface.get_rect(center=pos.astuple())
        self.screen.blit(text_surface, text_rect)

    def mouse_on_node(self, pos : Point):
        """
        Check if mouse_pos (in pos argument) is currently inside a node. If yes,
        returns id of corresponding node, otherwise returns -1
        """
        # Check if mouse is currently above a node
        for id in self.node_centers:
            actual_pos = self.node_centers[id].translate(self.screen_offset)
            if actual_pos.dist(pos) <= self.NODE_SIZE:
                return id
        return -1

    # ==== CHAT RELATED ===
    def handle_commands(self, message : str, source : str):
        """
        Handles any and all commands. Returns True if a command was executed and false otherwise.
        """
        ind = message.find("/")
        if ind != -1:
            message = message[ind:]
            if source == "BaseChat":
                n_ind = message.find("\n")
                quote_ind = message.find("\"")
                if n_ind != -1:
                    message = message[:n_ind]
                elif quote_ind != -1:
                    message = message[:quote_ind]
            
            command = message[1:].split()[0]
            msg = " ".join(message[1:].split()[1:])
            params = msg.split(",")

            if command == "help":
                self.chatbots["BaseChat"].update_decoration("GRAPH", str(self.graph))
                self.receive_text(self.chatbots["BaseChat"](msg), "BaseChat")
            
            if command == "addnode":
                concept = params[0]
                new_id = (max(self.graph.V.keys()) + 1) if self.graph.V else 0
                self.graph.add_node(new_id, concept)

                screen_center = Point(self.width // 2, self.height // 2)
                self.node_centers[new_id] = (screen_center - self.screen_offset)

                self.receive_text(f"Added node with ID {new_id} for concept '{concept}'", "System")

            elif command == "addedge":
                id1, id2 = int(params[0]), int(params[1])
                if id1 in self.graph.V and id2 in self.graph.V:
                    self.graph.V[id1].forward_neighbors.append(id2)
                    self.graph.V[id2].backward_neighbors.append(id1)
                    self.graph.E.append((id1, id2))
                    self.receive_text(f"Added edge from ID {id1} to ID {id2}", "System")
                else:
                    self.receive_text("Invalid node IDs provided", "System")
            return True
        return False

    def receive_text(self, message : str, source : str):
        """
        Receive text from any source
        """

        assert source in self.chat_colors, "Not a valid source for message"

        def log(message, source):
            self.chat_log.log(f"{source}: {message}", self.chat_colors[source])
        
        if message.find("\n") != -1:
            for line in message.split("\n"):
                log(line, source)
        else:
            log(message, source)

        if source in ["User", "BaseChat"]: # Only user and base chat can do commands
            if not self.handle_commands(message, source):
                # If the message was not a command
                self.chatbots["Tutor"].update_decoration("LEARNED CONCEPTS", self.graph.get_tagged_node_names())
                self.receive_text(self.chatbots["Tutor"](message), "Tutor")

    def run(self):
        chat_input = "" # Buffer for the chat

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                # Chatbox controls
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self.receive_text(chat_input, "User")
                        chat_input = ""
                    elif event.key == pygame.K_BACKSPACE:
                        chat_input = chat_input[:-1]
                    else:
                        chat_input += event.unicode

                # Graph controls
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = Point(*pygame.mouse.get_pos())
                    # First check for button presses
                    button_pressed = self.check_button_clicks(mouse_pos)
                    if button_pressed:
                        self.buttons[button_pressed].click()
                    else:
                        mouse_node = self.mouse_on_node(mouse_pos) # -1 if no node, otherwise has an id
                        if mouse_node == -1:
                            self.dragging_mode = True
                            self.dragging_start_pos = mouse_pos
                            self.dragging_screen_start = self.screen_offset
                        elif self.move_mode:
                            if mouse_node != -1:
                                self.selected_node = mouse_node
                                self.dragging_start_pos = mouse_pos
                            else:
                                self.selected_node = None
                        else: # Select node
                            self.selected_node = mouse_node

                elif event.type == pygame.MOUSEMOTION:
                    if self.move_mode:
                        if self.selected_node is not None and self.dragging_start_pos is not None:
                            mouse_pos = Point(*pygame.mouse.get_pos())
                            delta = mouse_pos - self.dragging_start_pos
                            self.node_centers[self.selected_node] += delta
                            self.dragging_start_pos = mouse_pos
                elif event.type == pygame.MOUSEBUTTONUP:
                    if self.dragging_mode:
                        self.dragging_mode = False
                    if self.move_mode:
                        if self.selected_node is not None:
                            self.selected_node = None
                            self.dragging_start_pos = None       

            self.screen.fill((0, 0, 0))

            # Chat box surface
            chat_surface = self.font.render(chat_input, True, (255, 255, 255))
            self.screen.blit(chat_surface, (10, self.height - self.font.get_height()))
            self.chat_log.draw(self.screen, 10, self.height - self.font.get_height() * 2)

            # Draw edges with arrows
            for edge in self.graph.E:
                start_node = self.graph.V[edge[0]]
                end_node = self.graph.V[edge[1]]
                self.draw_arrow(self.node_centers[start_node.id], self.node_centers[end_node.id])

            # Draw nodes with text
            for node in self.graph.V.values():
                self.draw_node(self.node_centers[node.id], node.display_text, node.id)

            # Screen moving
            if self.dragging_mode:
                self.screen_offset = self.dragging_screen_start + (self.dragging_start_pos - Point(*pygame.mouse.get_pos()))

            # Buttons
            for key in self.buttons:
                self.buttons[key].draw(self.screen, self.font)

            pygame.display.flip()

        pygame.quit()

# Example usage
if __name__ == "__main__":
    graph = DirectedGraph()
    #graph.add_node(0, "A", [1])
    #graph.add_node(1, "B", [2])
    #graph.add_node(2, "C", [])

    explorer = GraphExplorer(graph)
    explorer.run()
        


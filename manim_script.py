from manim import *
import random
import numpy as np

import math

class PythagorasTheorem(Scene):
    def construct(self):
        # 1. Title and Setup
        title = Text("Pythagoras Theorem").to_edge(UP)
        self.play(Write(title))

        # Define triangle vertices (3-4-5 triangle)
        # Side a = 3, Side b = 4, Side c = 5
        p_top = np.array([0, 3, 0])
        p_origin = np.array([0, 0, 0])
        p_right = np.array([4, 0, 0])

        triangle = Polygon(p_top, p_origin, p_right, color=WHITE)
        triangle.move_to(ORIGIN).shift(LEFT * 1.5 + DOWN * 0.5)
        
        # Get shifted coordinates for square placement
        v = triangle.get_vertices()
        # v[0] is top, v[1] is origin, v[2] is right
        
        # 2. Labels
        labels = VGroup(
            Text("a").next_to(triangle, LEFT, buff=0.2),
            Text("b").next_to(triangle, DOWN, buff=0.2),
            Text("c").move_to(triangle.get_center() + UR * 0.3)
        )

        self.play(Create(triangle))
        self.play(Write(labels))
        self.wait(0.5)

        # 3. Squares on sides
        # Square on side 'a' (length 3)
        sq_a = Square(side_length=3, color=BLUE, fill_opacity=0.5)
        sq_a.next_to(triangle, LEFT, buff=0)

        # Square on side 'b' (length 4)
        sq_b = Square(side_length=4, color=GREEN, fill_opacity=0.5)
        sq_b.next_to(triangle, DOWN, buff=0)

        # Square on side 'c' (length 5)
        sq_c = Square(side_length=5, color=RED, fill_opacity=0.5)
        # Calculate angle of hypotenuse
        angle = math.atan2(3, 4)
        sq_c.rotate(-angle)
        # Position sq_c on the hypotenuse
        hyp_midpoint = (v[0] + v[2]) / 2
        # Normal vector to hypotenuse to push square outwards
        normal = np.array([3, 4, 0]) / 5
        sq_c.move_to(hyp_midpoint + normal * 2.5)

        squares = VGroup(sq_a, sq_b, sq_c)

        # 4. Group Animations
        # Animate squares appearing one by one using the .animate syntax
        self.play(squares[0].animate.set_fill(opacity=0.8), run_time=1)
        self.play(squares[1].animate.set_fill(opacity=0.8), run_time=1)
        self.play(squares[2].animate.set_fill(opacity=0.8), run_time=1)

        # 5. Formula
        # Using Text only as per constraints
        formula = Text("a^2 + b^2 = c^2").to_edge(RIGHT, buff=1)
        
        self.play(Write(formula))
        self.play(formula.animate.scale(1.2).set_color(YELLOW))
        self.play(formula.animate.scale(1/1.2))

        # Final display
        self.wait(2)
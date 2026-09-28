#!/usr/bin/env python3
"""Zero Tower Battle - Leaderboard"""
class Leaderboard:
    def __init__(self):
        self.top_scores = []
        
    def add_score(self, score):
        self.top_scores.append(score)
        self.top_scores.sort(reverse=True)
        self.top_scores = self.top_scores[:10]


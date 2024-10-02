from typing import List

# Define the Enhancement class
class Enhancement:
    def __init__(self, name: str, eligible_keywords: List[str], points: int=0, description: str=None):
        self.name = name
        self.eligible_keywords = set(eligible_keywords)  # Keywords that the Character must have to receive this Enhancement
        self.points = points  # Points cost of the Enhancement (if applicable)
        self.description = description  # Description of the Enhancement

    def __str__(self):
        return f"{self.name} ({self.points} points)\nEligible Keywords: {self.eligible_keywords}\n{self.description}"

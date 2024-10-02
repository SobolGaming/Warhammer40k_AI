# Define the Enhancement class
class Enhancement:
    def __init__(self, name, eligible_keywords, points=0):
        self.name = name
        self.eligible_keywords = set(eligible_keywords)  # Keywords that the Character must have to receive this Enhancement
        self.points = points  # Points cost of the Enhancement (if applicable)
from django.core.management.base import BaseCommand
from core.ai.rag import answer_general_question

class Command(BaseCommand):
    help = "Ask the knowledge base (Pinecone) and print the answer"

    def add_arguments(self, parser):
        parser.add_argument("q", type=str)

    def handle(self, *args, **opts):
        print(answer_general_question(opts["q"]))

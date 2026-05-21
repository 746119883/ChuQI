from django.shortcuts import render, get_object_or_404
from .models import Note


def note_list(request):
    notes = Note.objects.select_related('author').all()
    return render(request, 'notes/list.html', {'notes': notes})


def note_detail(request, pk):
    note = get_object_or_404(Note.objects.select_related('author'), pk=pk)
    return render(request, 'notes/detail.html', {'note': note})

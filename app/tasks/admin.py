from django.contrib import admin
from .models import TaskList, Task


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    readonly_fields = ('completed_at', 'completed_by', 'created_at')


@admin.register(TaskList)
class TaskListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'is_shared', 'task_count', 'updated_at')
    list_filter = ('is_shared', 'owner')
    search_fields = ('name',)
    inlines = [TaskInline]

    @admin.display(description='任务数')
    def task_count(self, obj):
        return obj.tasks.count()


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'list', 'title', 'completed', 'completed_by', 'created_at')
    list_filter = ('completed', 'list')
    search_fields = ('title',)

from datetime import timedelta

from django.contrib.postgres.fields import ArrayField, JSONField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.signals import post_init, pre_save
from django.dispatch import receiver
from django.utils import timezone
from localized_fields.fields import LocalizedField

from ..caluma_core.models import ChoicesCharField, SlugModel, UUIDModel
from . import managers, validators


class Task(SlugModel):
    TYPE_SIMPLE = "simple"
    TYPE_COMPLETE_WORKFLOW_FORM = "complete_workflow_form"
    TYPE_COMPLETE_TASK_FORM = "complete_task_form"

    TYPE_CHOICES = (TYPE_SIMPLE, TYPE_COMPLETE_WORKFLOW_FORM, TYPE_COMPLETE_TASK_FORM)
    TYPE_CHOICES_TUPLE = (
        (TYPE_SIMPLE, "Task which can simply be marked as completed."),
        (TYPE_COMPLETE_WORKFLOW_FORM, "Task to complete a defined workflow form."),
        (TYPE_COMPLETE_TASK_FORM, "Task to complete a defined task form."),
    )

    name = LocalizedField(blank=False, null=False, required=False)
    description = LocalizedField(blank=True, null=True, required=False)
    type = ChoicesCharField(choices=TYPE_CHOICES_TUPLE, max_length=50)
    meta = JSONField(default=dict)
    address_groups = models.TextField(
        blank=True,
        null=True,
        help_text="Group jexl returning what group(s) derived work items will be addressed to.",
    )
    control_groups = models.TextField(
        blank=True,
        null=True,
        help_text="Group jexl returning what group(s) derived work items will be assigned to for controlling.",
    )
    is_archived = models.BooleanField(default=False)
    form = models.ForeignKey(
        "caluma_form.Form",
        on_delete=models.DO_NOTHING,
        related_name="tasks",
        blank=True,
        null=True,
    )
    lead_time = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Time in seconds task may take to be processed.",
    )
    is_multiple_instance = models.BooleanField(
        default=False,
        help_text="Allows creating multiple work items for this task using the `CreateWorkItem` mutation. If true, one work item will be created for each entry in `address_groups`.",
    )

    def calculate_deadline(self):
        if self.lead_time is not None:
            return timezone.now() + timedelta(seconds=self.lead_time)
        return None

    class Meta:
        indexes = [GinIndex(fields=["meta"])]


class Workflow(SlugModel):
    name = LocalizedField(blank=False, null=False, required=False)
    description = LocalizedField(blank=True, null=True, required=False)
    meta = JSONField(default=dict)
    is_published = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    start_tasks = models.ManyToManyField(
        Task, related_name="+", help_text="Starting task(s) of the workflow."
    )
    allow_all_forms = models.BooleanField(
        default=False, help_text="Allow workflow to be started with any form"
    )
    allow_forms = models.ManyToManyField(
        "caluma_form.Form",
        help_text="List of forms which are allowed to start workflow with",
        related_name="workflows",
        blank=True,
    )

    @property
    def flows(self):
        return Flow.objects.filter(pk__in=self.task_flows.values("flow"))

    class Meta:
        indexes = [GinIndex(fields=["meta"])]


class Flow(UUIDModel):
    next = models.TextField()


class TaskFlow(UUIDModel):
    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name="task_flows"
    )
    task = models.ForeignKey(Task, related_name="task_flows", on_delete=models.CASCADE)
    flow = models.ForeignKey(Flow, related_name="task_flows", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("workflow", "task")


class Case(UUIDModel):
    objects = managers.CaseManager()

    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = (STATUS_RUNNING, STATUS_COMPLETED, STATUS_CANCELED)
    STATUS_CHOICE_TUPLE = (
        (STATUS_RUNNING, "Case is running and work items need to be completed."),
        (STATUS_COMPLETED, "Case is done."),
        (STATUS_CANCELED, "Case is cancelled."),
    )

    family = models.ForeignKey(
        "self",
        help_text="Family id which case belongs to.",
        null=True,
        on_delete=models.CASCADE,
        related_name="+",
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Time when case has either been canceled or completed",
    )
    closed_by_user = models.CharField(max_length=150, blank=True, null=True)
    closed_by_group = models.CharField(max_length=150, blank=True, null=True)

    workflow = models.ForeignKey(
        Workflow, related_name="cases", on_delete=models.DO_NOTHING
    )
    status = ChoicesCharField(choices=STATUS_CHOICE_TUPLE, max_length=50, db_index=True)
    meta = JSONField(default=dict)
    document = models.OneToOneField(
        "caluma_form.Document",
        on_delete=models.PROTECT,
        related_name="case",
        blank=True,
        null=True,
    )

    class Meta:
        indexes = [GinIndex(fields=["meta"])]


@receiver(post_init, sender=Case)
def set_case_family(sender, instance, **kwargs):
    """
    Ensure case has the family pointer set.

    This sets the case's family if not overruled or set already.
    """
    if instance.family_id is None:
        instance.family = instance


class WorkItem(UUIDModel):
    STATUS_READY = "ready"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELED = "canceled"
    STATUS_SKIPPED = "skipped"

    STATUS_CHOICES = (STATUS_READY, STATUS_COMPLETED, STATUS_CANCELED)
    STATUS_CHOICE_TUPLE = (
        (STATUS_READY, "Task is ready to be processed."),
        (STATUS_COMPLETED, "Task is done."),
        (STATUS_CANCELED, "Task is cancelled."),
        (STATUS_SKIPPED, "Task is skipped."),
    )

    name = LocalizedField(
        blank=False,
        null=False,
        required=False,
        help_text="Will be set from Task, if not provided.",
    )
    description = LocalizedField(
        blank=True,
        null=True,
        required=False,
        help_text="Will be set from Task, if not provided.",
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Time when work item has either been canceled or completed",
    )
    closed_by_user = models.CharField(max_length=150, blank=True, null=True)
    closed_by_group = models.CharField(max_length=150, blank=True, null=True)
    deadline = models.DateTimeField(blank=True, null=True)

    task = models.ForeignKey(
        Task, on_delete=models.DO_NOTHING, related_name="work_items"
    )
    status = ChoicesCharField(choices=STATUS_CHOICE_TUPLE, max_length=50, db_index=True)
    meta = JSONField(default=dict)

    addressed_groups = ArrayField(
        models.CharField(max_length=150),
        default=list,
        help_text=(
            "Offer work item to be processed by a group of users, "
            "such are not committed to process it though."
        ),
    )

    controlling_groups = ArrayField(
        models.CharField(max_length=150),
        default=list,
        help_text="List of groups this work item is assigned to for controlling.",
    )

    assigned_users = ArrayField(
        models.CharField(max_length=150),
        default=list,
        help_text="Users responsible to undertake given work item.",
    )

    case = models.ForeignKey(Case, related_name="work_items", on_delete=models.CASCADE)
    child_case = models.OneToOneField(
        Case,
        related_name="parent_work_item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Defines case of a sub-workflow",
    )

    document = models.OneToOneField(
        "caluma_form.Document",
        on_delete=models.PROTECT,
        related_name="work_item",
        blank=True,
        null=True,
    )

    def validate_for_complete(self, user):
        validators.WorkItemValidator().validate(
            status=self.status,
            child_case=self.child_case,
            task=self.task,
            case=self.case,
            document=self.document,
            user=user,
        )

    def pre_complete(self, user):
        self.validate_for_complete(user)
        self.status = models.WorkItem.STATUS_COMPLETED
        self.closed_at = timezone.now()
        self.closed_by_user = user.username
        self.closed_by_group = user.group

    def post_complete(self, user):
        instance = super().update(instance, validated_data)
        user = self.context["request"].user
        case = instance.case

        if not self._can_continue(instance, instance.task):
            return instance

        flow = models.Flow.objects.filter(task_flows__task=instance.task_id).first()
        flow_referenced_tasks = models.Task.objects.filter(task_flows__flow=flow)

        all_complete = all(
            self._can_continue(instance, task) for task in flow_referenced_tasks
        )

        if flow and all_complete:
            jexl = FlowJexl()
            result = jexl.evaluate(flow.next)
            if not isinstance(result, list):
                result = [result]

            tasks = models.Task.objects.filter(pk__in=result)

            work_items = utils.bulk_create_work_items(tasks, case, user, instance)

            for work_item in work_items:  # pragma: no cover
                self.send_event(events.created_work_item, work_item=work_item)
        else:
            # no more tasks, mark case as complete
            case.status = models.Case.STATUS_COMPLETED
            case.closed_at = timezone.now()
            case.closed_by_user = user.username
            case.closed_by_group = user.group
            case.save()
            self.send_event(events.completed_case, case=case)

        self.send_event(events.completed_work_item, work_item=instance)

        return instance

    class Meta:
        indexes = [
            GinIndex(fields=["addressed_groups"]),
            GinIndex(fields=["assigned_users"]),
            GinIndex(fields=["meta"]),
        ]


@receiver(pre_save, sender=WorkItem)
def set_name_and_description(sender, instance, **kwargs):
    """
    Ensure WorkItem has a name and description set.

    Default to values from Task.
    """
    if not any(instance.name.values()):
        instance.name = instance.task.name
    if not any(instance.description.values()):
        instance.description = instance.task.description

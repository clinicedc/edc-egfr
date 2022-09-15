from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from edc_lab_panel.model_mixin_factory import reportable_result_model_mixin_factory
from edc_registration.models import RegisteredSubject
from edc_reportable.units import EGFR_UNITS, PERCENT
from edc_reportable.utils import get_reference_range_collection_name

from ..egfr import Egfr


class EgfrModelMixin(
    reportable_result_model_mixin_factory(
        utest_id="egfr",
        verbose_name="eGFR",
        decimal_places=4,
        default_units=EGFR_UNITS,
        max_digits=8,
        units_choices=((EGFR_UNITS, EGFR_UNITS),),
    ),
    reportable_result_model_mixin_factory(
        utest_id="egfr_drop",
        verbose_name="eGFR Drop",
        decimal_places=4,
        default_units=PERCENT,
        max_digits=10,
        units_choices=((PERCENT, PERCENT),),
    ),
    models.Model,
):

    """Declared with a bloodresult RFT CRF model.

    As a lab result CRF, expects subject_visit, requisition
    and report_datetime.

    See edc_lab_result, edc_crf.
    """

    percent_drop_threshold: Optional[float] = 20
    baseline_timepoint: Optional[int] = 0
    egfr_formula_name: Optional[str] = None

    def save(self, *args, **kwargs):
        egfr = Egfr(**self.egfr_options)
        self.egfr_value = egfr.egfr_value
        self.egfr_units = egfr.egfr_units
        self.egfr_grade = egfr.egfr_grade
        self.egfr_drop_value = egfr.egfr_drop_value
        self.egfr_drop_units = egfr.egfr_drop_units
        self.egfr_drop_grade = egfr.egfr_drop_grade
        super().save(*args, **kwargs)

    @property
    def egfr_options(self) -> dict:
        rs = RegisteredSubject.objects.get(
            subject_identifier=self.subject_visit.subject_identifier
        )
        return dict(
            calling_crf=self,
            dob=rs.dob,
            gender=rs.gender,
            ethnicity=rs.ethnicity,
            percent_drop_threshold=self.percent_drop_threshold,
            value_threshold=45.0000,
            report_datetime=self.report_datetime,
            baseline_egfr_value=self.get_baseline_egfr_value(),
            formula_name=self.egfr_formula_name,
            reference_range_collection_name=get_reference_range_collection_name(self),
        )

    def get_baseline_egfr_value(self) -> Optional[float]:
        """Returns a baseline or reference eGFR value.

        Expects a longitudinal / CRF model with attrs subject_visit.
        """
        egfr_value = None
        with transaction.atomic():
            subject_visit = self.subject_visit.__class__.objects.get(
                appointment__subject_identifier=self.subject_visit.subject_identifier,
                appointment__visit_schedule_name=self.subject_visit.visit_schedule_name,
                appointment__schedule_name=self.subject_visit.schedule_name,
                appointment__timepoint=self.baseline_timepoint,
                visit_code_sequence=0,
            )
        with transaction.atomic():
            try:
                egfr_value = self.__class__.objects.get(subject_visit=subject_visit).egfr_value
            except ObjectDoesNotExist:
                pass
        return egfr_value

    class Meta:
        abstract = True

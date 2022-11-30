import datetime
from collections import ChainMap

import ddt
import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from pytz import UTC

from conftest import TEST_DOMAIN
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory
from course_discovery.apps.course_metadata.algolia_models import AlgoliaProxyCourse, AlgoliaProxyProgram
from course_discovery.apps.course_metadata.choices import ExternalProductStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRunStatus, CourseType
from course_discovery.apps.course_metadata.tests.factories import (
    AdditionalMetadataFactory, CourseFactory, CourseRunFactory, CourseTypeFactory, DegreeAdditionalMetadataFactory,
    DegreeFactory, LevelTypeFactory, OrganizationFactory, ProductMetaFactory, ProgramFactory, ProgramTypeFactory,
    SeatFactory, SeatTypeFactory, SubjectFactory
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag


class AlgoliaProxyCourseFactory(CourseFactory):
    class Meta:
        model = AlgoliaProxyCourse


class AlgoliaProxyProgramFactory(ProgramFactory):
    class Meta:
        model = AlgoliaProxyProgram


class TestAlgoliaDataMixin():
    ONE_MONTH_AGO = datetime.datetime.now(UTC) - datetime.timedelta(days=30)
    YESTERDAY = datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    TOMORROW = datetime.datetime.now(UTC) + datetime.timedelta(days=1)
    IN_THREE_DAYS = datetime.datetime.now(UTC) + datetime.timedelta(days=3)
    IN_FIFTEEN_DAYS = datetime.datetime.now(UTC) + datetime.timedelta(days=15)
    IN_TWO_MONTHS = datetime.datetime.now(UTC) + datetime.timedelta(days=60)

    def create_current_upgradeable_course(self, **kwargs):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        current_upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published,
            **kwargs
        )
        SeatFactory(
            course_run=current_upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.TOMORROW,
            price=10
        )
        return course

    def create_upgradeable_course_ending_soon(self, **kwargs):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_THREE_DAYS,
            enrollment_end=self.IN_THREE_DAYS,
            status=CourseRunStatus.Published,
            **kwargs
        )

        SeatFactory(
            course_run=upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.TOMORROW,
            price=10
        )
        return course

    def create_upgradeable_course_starting_soon(self, **kwargs):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.TOMORROW,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published,
            **kwargs
        )

        SeatFactory(
            course_run=upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.IN_FIFTEEN_DAYS,
            price=10
        )
        return course

    def create_current_non_upgradeable_course(self, **kwargs):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)

        non_upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published,
            **kwargs
        )
        # not upgradeable because upgrade_deadline has passed
        SeatFactory(
            course_run=non_upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.YESTERDAY,
            price=10
        )
        return course

    def create_upcoming_non_upgradeable_course(self, additional_days=0, **kwargs):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        future_course_run = CourseRunFactory(
            course=course,
            start=self.IN_THREE_DAYS + datetime.timedelta(days=additional_days),
            end=self.IN_FIFTEEN_DAYS + datetime.timedelta(days=additional_days),
            enrollment_end=self.IN_THREE_DAYS + datetime.timedelta(days=additional_days),
            status=CourseRunStatus.Published,
            **kwargs
        )
        SeatFactory(
            course_run=future_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.YESTERDAY,
            price=10
        )
        return course

    def create_course_with_basic_active_course_run(self, **kwargs):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)

        course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.YESTERDAY,
            status=CourseRunStatus.Published,
            **kwargs
        )
        SeatFactory(
            course_run=course_run,
            type=SeatTypeFactory.audit(),
        )
        return course

    def attach_published_course_run(self, course, run_type="archived", **kwargs):
        if run_type == 'current and ends within two weeks':
            course_start = self.ONE_MONTH_AGO
            course_end = self.TOMORROW
        elif run_type == 'current and ends after two weeks':
            course_start = self.ONE_MONTH_AGO
            course_end = self.IN_TWO_MONTHS
        elif run_type == 'upcoming':
            course_start = self.TOMORROW
            course_end = self.IN_TWO_MONTHS
        elif run_type == 'archived':
            course_start = self.ONE_MONTH_AGO
            course_end = self.YESTERDAY

        return CourseRunFactory(
            course=course,
            start=course_start,
            end=course_end,
            status=CourseRunStatus.Published,
            **kwargs
        )


@override_settings(SETTING_DICT=ChainMap({'AUTO_INDEXING': 'False'}, settings.ALGOLIA))
class TestAlgoliaProxyWithEdxPartner(TestCase, TestAlgoliaDataMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner.objects.all().delete()
        Site.objects.all().delete()
        cls.site = SiteFactory(id=settings.SITE_ID, domain=TEST_DOMAIN)
        cls.edxPartner = PartnerFactory(site=cls.site)
        cls.edxPartner.name = 'edX'


@ddt.ddt
@pytest.mark.django_db
class TestAlgoliaProxyCourse(TestAlgoliaProxyWithEdxPartner):

    def test_should_index(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory())
        assert course.should_index

    def test_do_not_index_if_no_owners(self):
        course = self.create_course_with_basic_active_course_run()
        assert not course.should_index

    def test_do_not_index_if_owner_missing_logo(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory(logo_image=None))
        assert not course.should_index

    def test_do_not_index_if_no_url_slug(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory())
        for url_slug in course.url_slug_history.all():
            url_slug.is_active = False
            url_slug.save()
        assert not course.should_index

    def test_do_not_index_if_partner_not_edx(self):
        course = self.create_course_with_basic_active_course_run()
        course.partner = PartnerFactory()
        course.authoring_organizations.add(OrganizationFactory())
        assert not course.should_index

    def test_do_not_index_if_no_active_course_run(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        course.authoring_organizations.add(OrganizationFactory())
        assert not course.should_index

    def test_do_not_index_if_active_course_run_is_hidden(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory())
        for course_run in course.course_runs.all():
            course_run.hidden = True
            course_run.save()
        assert not course.should_index

    def test_index_if_non_active_course_run_is_hidden(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory())
        non_upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published,
            hidden=True
        )
        # not upgradeable because upgrade_deadline has passed
        SeatFactory(
            course_run=non_upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.YESTERDAY,
            price=10
        )
        assert course.should_index

    def test_current_and_upgradeable_beats_just_upgradeable(self):
        course_1 = self.create_current_upgradeable_course()
        course_2 = self.create_upgradeable_course_ending_soon()
        course_3 = self.create_upgradeable_course_starting_soon()
        assert course_1.availability_rank < course_2.availability_rank
        assert course_1.availability_rank < course_3.availability_rank
        assert course_2.availability_rank == course_3.availability_rank

    def test_upgradeable_beats_just_current(self):
        course_1 = self.create_upgradeable_course_ending_soon()
        course_2 = self.create_current_non_upgradeable_course()
        assert course_1.availability_rank < course_2.availability_rank

    def test_current_non_upgradeable_beats_upcoming_non_upgradeable(self):
        course_1 = self.create_current_non_upgradeable_course()
        course_2 = self.create_upcoming_non_upgradeable_course()
        assert course_1.availability_rank < course_2.availability_rank

    def test_earliest_upcoming_wins(self):
        course_1 = self.create_upcoming_non_upgradeable_course()
        course_2 = self.create_upcoming_non_upgradeable_course(additional_days=1)
        assert course_1.availability_rank < course_2.availability_rank

    def test_active_course_run_beats_no_active_course_run(self):
        course_1 = self.create_course_with_basic_active_course_run()
        course_2 = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        CourseRunFactory(
            course=course_2,
            start=self.YESTERDAY,
            end=self.YESTERDAY,
            enrollment_end=self.YESTERDAY,
            status=CourseRunStatus.Published
        )
        assert course_1.availability_rank
        assert not course_2.availability_rank

    def test_course_availability_reflects_all_course_runs(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)

        self.attach_published_course_run(course=course, run_type="current and ends after two weeks")
        self.attach_published_course_run(course=course, run_type='upcoming')
        self.attach_published_course_run(course=course, run_type='archived')

        assert len(course.availability_level) == 3
        assert 'Available now' in course.availability_level
        assert 'Upcoming' in course.availability_level
        assert 'Archived' in course.availability_level

    def test_course_not_available_now_if_end_date_too_soon(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)

        self.attach_published_course_run(course=course, run_type="current and ends within two weeks")

        assert course.availability_level == ['Archived']

    def test_course_availability_empty_if_no_published_runs(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        CourseRunFactory(
            course=course,
            status=CourseRunStatus.Unpublished,
        )

        assert course.availability_level == []

    def test_spanish_courses_promoted_in_spanish_index(self):
        colombian_spanish = LanguageTag.objects.get(code='es-co')
        american_english = LanguageTag.objects.get(code='en-us')
        spanish_course = self.create_course_with_basic_active_course_run(language=colombian_spanish)
        english_course = self.create_course_with_basic_active_course_run(language=american_english)
        assert spanish_course.promoted_in_spanish_index
        assert not english_course.promoted_in_spanish_index

    @ddt.data(
        (CourseType.EXECUTIVE_EDUCATION_2U, 'Meta Product Title'),
        (CourseType.EXECUTIVE_EDUCATION_2U, None),
        (CourseType.BOOTCAMP_2U, None),
    )
    @ddt.unpack
    def test_product_meta_title(self, type_slug, expected_title):
        """
        Verify the meta title is returned only for ExecEd course type if product meta info is present.
        """
        course = AlgoliaProxyCourseFactory(
            partner=self.__class__.edxPartner,
            type=CourseTypeFactory(
                slug=type_slug
            ),
            additional_metadata=AdditionalMetadataFactory(product_meta=None)
        )
        if expected_title:
            course.additional_metadata.product_meta = ProductMetaFactory(
                title="Meta Product Title"
            )

        assert course.product_meta_title == expected_title

    @ddt.data(
        (ExternalProductStatus.Published, True),
        (ExternalProductStatus.Archived, False)
    )
    @ddt.unpack
    def test_product_external_status(self, external_status, should_index):
        """
        If an Exec Ed course has an external product status of "Archived", it should not be indexed
        """
        course = self.create_course_with_basic_active_course_run()
        course.type = CourseTypeFactory(slug=CourseType.EXECUTIVE_EDUCATION_2U)
        course.authoring_organizations.add(OrganizationFactory())
        course.additional_metadata = AdditionalMetadataFactory(product_status=external_status)
        assert course.should_index == should_index


@ddt.ddt
@pytest.mark.django_db
class TestAlgoliaProxyProgram(TestAlgoliaProxyWithEdxPartner):

    ONE_MONTH_AGO = datetime.datetime.now(UTC) - datetime.timedelta(days=30)
    YESTERDAY = datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    TOMORROW = datetime.datetime.now(UTC) + datetime.timedelta(days=1)
    IN_FIFTEEN_DAYS = datetime.datetime.now(UTC) + datetime.timedelta(days=15)
    IN_TWO_MONTHS = datetime.datetime.now(UTC) + datetime.timedelta(days=60)

    def attach_course_run(self, course, availability="Archived"):
        if availability == 'none':
            return CourseRunFactory(
                course=course,
                start=self.TOMORROW,
                end=self.IN_TWO_MONTHS,
                status=CourseRunStatus.Unpublished
            )
        elif availability == 'Available now':
            course_start = self.ONE_MONTH_AGO
            course_end = self.IN_FIFTEEN_DAYS
        elif availability == 'Upcoming':
            course_start = self.TOMORROW
            course_end = self.IN_TWO_MONTHS
        elif availability == 'Archived':
            course_start = self.ONE_MONTH_AGO
            course_end = self.YESTERDAY

        return CourseRunFactory(
            course=course,
            start=course_start,
            end=course_end,
            status=CourseRunStatus.Published
        )

    def attach_archived_course(self, program):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        CourseRunFactory(
            course=course,
            start=self.ONE_MONTH_AGO,
            end=self.YESTERDAY,
            status=CourseRunStatus.Published
        )
        return program.courses.add(course)

    def test_program_availability_reflects_all_unique_course_statuses(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)

        course_1 = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        self.attach_course_run(course=course_1, availability="Available now")
        self.attach_course_run(course=course_1, availability="Upcoming")
        program.courses.add(course_1)

        course_2 = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        self.attach_course_run(course=course_2, availability="Upcoming")
        self.attach_course_run(course=course_2, availability="Archived")
        program.courses.add(course_2)

        assert len(program.availability_level) == 3
        assert 'Available now' in program.availability_level
        assert 'Upcoming' in program.availability_level
        assert 'Archived' in program.availability_level

    @ddt.data('masters', 'bachelors', 'doctorate', 'license', 'certificate')
    def test_program_available_now(self, program_type_slug):
        program_type = ProgramTypeFactory()
        program_type.slug = program_type_slug
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner, type=program_type)

        assert program.availability_level == 'Available now'

    def test_program_not_available_if_no_published_runs(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        self.attach_course_run(course=course, availability="none")
        program.courses.add(course)

        assert program.availability_level == []

    def test_only_programs_with_spanish_courses_promoted_in_spanish_index(self):
        all_spanish_program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        mixed_language_program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        all_english_program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)

        colombian_spanish = LanguageTag.objects.get(code='es-co')
        american_english = LanguageTag.objects.get(code='en-us')

        spanish_course = self.create_course_with_basic_active_course_run(language=colombian_spanish)
        english_course = self.create_course_with_basic_active_course_run(language=american_english)

        all_spanish_program.courses.add(spanish_course)
        mixed_language_program.courses.add(spanish_course, english_course)
        all_english_program.courses.add(english_course)

        assert all_spanish_program.promoted_in_spanish_index
        assert mixed_language_program.promoted_in_spanish_index
        assert not all_english_program.promoted_in_spanish_index

    def test_should_index(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        program.authoring_organizations.add(OrganizationFactory())
        self.attach_archived_course(program=program)
        assert program.should_index

    def test_do_not_index_if_no_owners(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        self.attach_archived_course(program=program)
        assert not program.should_index

    def test_do_not_index_if_owner_missing_logo(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        program.authoring_organizations.add(OrganizationFactory(logo_image=None))
        self.attach_archived_course(program=program)
        assert not program.should_index

    def test_do_not_index_if_partner_not_edx(self):
        program = AlgoliaProxyProgramFactory(partner=PartnerFactory())
        program.authoring_organizations.add(OrganizationFactory())
        self.attach_archived_course(program=program)
        assert not program.should_index

    def test_do_not_index_if_not_active(self):
        unpublished_program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner,
                                                         status=ProgramStatus.Unpublished)
        unpublished_program.authoring_organizations.add(OrganizationFactory())
        self.attach_archived_course(program=unpublished_program)

        retired_program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner,
                                                     status=ProgramStatus.Retired)
        retired_program.authoring_organizations.add(OrganizationFactory())
        self.attach_archived_course(program=retired_program)

        deleted_program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner,
                                                     status=ProgramStatus.Deleted)
        deleted_program.authoring_organizations.add(OrganizationFactory())
        self.attach_archived_course(program=deleted_program)

        assert not unpublished_program.should_index
        assert not retired_program.should_index
        assert not deleted_program.should_index

    def test_do_not_index_if_hidden(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner, hidden=True)
        program.authoring_organizations.add(OrganizationFactory())
        self.attach_archived_course(program=program)
        assert not program.should_index

    def test_is_2u_degree_program(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        degree = DegreeFactory()
        degree.additional_metadata = DegreeAdditionalMetadataFactory()
        program.degree = degree
        assert program.is_2u_degree_program

    def test_is_not_2u_degree_program(self):
        program = AlgoliaProxyProgramFactory()
        assert not program.is_2u_degree_program

    @ddt.data(True, False)
    def test_program_overrides(self, has_overrides):
        # default
        american_english = LanguageTag.objects.get(code='en-us')
        introductory = LevelTypeFactory(name_t='Introductory')
        computer_science = SubjectFactory(name='Computer Science', partner=self.__class__.edxPartner)
        # overrides
        colombian_spanish = LanguageTag.objects.get(code='es-co')
        intermediate = LevelTypeFactory(name_t='Intermediate')
        business = SubjectFactory(name='Business', partner=self.__class__.edxPartner)

        program_data = {
            'partner': self.__class__.edxPartner,
            'language_override': None,
            'level_type_override': None,
            'primary_subject_override': None
        }
        if has_overrides:
            program_data['language_override'] = colombian_spanish
            program_data['level_type_override'] = intermediate
            program_data['primary_subject_override'] = business

        program = AlgoliaProxyProgramFactory(**program_data)
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner, level_type=introductory)
        course.subjects.add(computer_science)
        course_run = CourseRunFactory(
            course=course,
            start=self.ONE_MONTH_AGO,
            end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published,
            language=american_english
        )
        SeatFactory(
            course_run=course_run,
            type=SeatTypeFactory.audit(),
        )
        program.courses.add(course)

        if has_overrides:
            assert program.active_languages == ['Spanish']
            assert program.levels == ['Intermediate']
            assert program.subject_names == ['Business']
        else:
            assert program.active_languages == ['English']
            assert program.levels == ['Introductory']
            assert program.subject_names == ['Computer Science']

    def test_program_tags(self):
        program = AlgoliaProxyProgramFactory()
        course1 = AlgoliaProxyCourseFactory()
        course2 = AlgoliaProxyCourseFactory()
        course1.topics.add('course1_topic1', 'course1_topic2', 'generic')
        course2.topics.add('course2_topic1', 'course2_topic2', 'generic')
        program.labels.add('program_label1', 'program_label2', 'generic')
        program.courses.add(course1, course2)
        expected_tags = [
            'generic', 'course1_topic1', 'program_label2', 'course1_topic2',
            'course2_topic1', 'course2_topic2', 'program_label1'
        ]
        assert sorted(program.tags) == sorted(expected_tags)

    def test_product_meta_title(self):
        """
        Verify the meta title for programs is None.
        """
        program = AlgoliaProxyProgramFactory()
        assert program.product_meta_title is None

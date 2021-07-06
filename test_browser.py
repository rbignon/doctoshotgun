import pytest
from requests.adapters import Response
import responses
from html import escape
import json
import datetime
from woob.browser.browsers import Browser
from woob.browser.exceptions import ServerError
from doctoshotgun import DoctolibDE, DoctolibFR, CenterBookingPage

# globals
FIXTURES_FOLDER = "test_fixtures"


@responses.activate
def test_find_centers_fr_returns_503_should_continue(tmp_path):
    """
    Check that find_centers doesn't raise a ServerError in case of 503 HTTP response
    """
    docto = DoctolibFR("roger.phillibert@gmail.com",
                       "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/vaccination-covid-19/Paris?ref_visit_motive_ids%5B%5D=6970&ref_visit_motive_ids%5B%5D=6971&ref_visit_motive_ids%5B%5D=8192&ref_visit_motive_ids%5B%5D=7005&ref_visit_motive_ids%5B%5D=7004&ref_visit_motive_ids%5B%5D=8193&ref_visit_motive_ids%5B%5D=7945&ref_visit_motive_ids%5B%5D=7107&ref_visit_motive_ids%5B%5D=7108&page=1",
        status=503
    )

    # this should not raise an exception
    for _ in docto.find_centers(["Paris"]):
        pass


@responses.activate
def test_find_centers_de_returns_503_should_continue(tmp_path):
    """
    Check that find_centers doesn't raise a ServerError in case of 503 HTTP response
    """
    docto = DoctolibDE("roger.phillibert@gmail.com",
                       "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/impfung-covid-19-corona/M%C3%BCnchen?ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6769&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=6937&ref_visit_motive_ids%5B%5D=7978&ref_visit_motive_ids%5B%5D=7109&ref_visit_motive_ids%5B%5D=7110&page=1",
        status=503
    )

    # this should not raise an exception
    for _ in docto.find_centers(["München"]):
        pass


@responses.activate
def test_find_centers_de_returns_520_should_continue(tmp_path):
    """
    Check that find_centers doesn't raise a ServerError in case of 503 HTTP response
    """
    docto = DoctolibDE("roger.phillibert@gmail.com",
                       "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/impfung-covid-19-corona/M%C3%BCnchen?ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6769&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=6937&ref_visit_motive_ids%5B%5D=7978&ref_visit_motive_ids%5B%5D=7109&ref_visit_motive_ids%5B%5D=7110&page=1",
        status=520
    )

    # this should not raise an exception
    for _ in docto.find_centers(["München"]):
        pass


@responses.activate
def test_find_centers_fr_returns_502_should_fail(tmp_path):
    """
    Check that find_centers raises an error in case of non-whitelisted status code
    """
    docto = DoctolibFR("roger.phillibert@gmail.com",
                       "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/vaccination-covid-19/Paris?ref_visit_motive_ids%5B%5D=6970&ref_visit_motive_ids%5B%5D=6971&ref_visit_motive_ids%5B%5D=8192&ref_visit_motive_ids%5B%5D=7005&ref_visit_motive_ids%5B%5D=7004&ref_visit_motive_ids%5B%5D=8193&ref_visit_motive_ids%5B%5D=7945&ref_visit_motive_ids%5B%5D=7107&ref_visit_motive_ids%5B%5D=7108&page=1",
        status=502
    )

    # this should raise an exception
    with pytest.raises(ServerError):
        for _ in docto.find_centers(["Paris"]):
            pass


@responses.activate
def test_find_centers_de_returns_502_should_fail(tmp_path):
    """
    Check that find_centers raises an error in case of non-whitelisted status code
    """
    docto = DoctolibDE("roger.phillibert@gmail.com",
                       "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/impfung-covid-19-corona/M%C3%BCnchen?ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6769&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=6937&ref_visit_motive_ids%5B%5D=7978&ref_visit_motive_ids%5B%5D=7109&ref_visit_motive_ids%5B%5D=7110&page=1",
        status=502
    )

    # this should raise an exception
    with pytest.raises(ServerError):
        for _ in docto.find_centers(["München"]):
            pass


@responses.activate
def test_book_slots_should_succeed(tmp_path):
    """
    Check that try_to_book calls all services successfully
    """
    docto = DoctolibDE("roger.phillibert@gmail.com",
                       "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"
    docto.patient = {
        "id": "patient-id",
        "first_name": "Roger",
        "last_name": "Phillibert"
    }

    mock_search_result_id = {
        "searchResultId": 1234567
    }

    mock_search_result_id_escaped_json = escape(
        json.dumps(mock_search_result_id, separators=(',', ':')))

    responses.add(
        responses.GET,
        "https://127.0.0.1/impfung-covid-19-corona/K%C3%B6ln?ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6769&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=6937&ref_visit_motive_ids%5B%5D=7978&ref_visit_motive_ids%5B%5D=7109&ref_visit_motive_ids%5B%5D=7110&page=1",
        status=200,
        body="<div class='js-dl-search-results-calendar' data-props='{dataProps}'></div>".format(
            dataProps=mock_search_result_id_escaped_json)
    )

    with open(FIXTURES_FOLDER + '/search_result.json') as json_file:
        mock_search_result = json.load(json_file)

        responses.add(
            responses.GET,
            "https://127.0.0.1/search_results/1234567.json?limit=4&ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6769&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=6937&ref_visit_motive_ids%5B%5D=7978&ref_visit_motive_ids%5B%5D=7109&ref_visit_motive_ids%5B%5D=7110&speciality_id=5494&search_result_format=json",
            status=200,
            body=json.dumps(mock_search_result)
        )

    with open(FIXTURES_FOLDER + '/doctor_response.json') as json_file:
        mock_doctor_response = json.load(json_file)

        responses.add(
            responses.GET,
            "https://127.0.0.1/allgemeinmedizin/koeln/dr-dre?insurance_sector=public",
            status=200,
            body=json.dumps(mock_doctor_response)
        )

    responses.add(
        responses.GET,
        "https://127.0.0.1/booking/dr-dre.json",
        status=200,
        body=json.dumps(mock_doctor_response)
    )

    with open(FIXTURES_FOLDER + '/availabilities.json') as json_file:
        mock_availabilities = json.load(json_file)

        responses.add(
            responses.GET,
            "https://127.0.0.1/availabilities.json?start_date=2021-06-01&visit_motive_ids=2920448&agenda_ids=&insurance_sector=public&practice_ids=234567&destroy_temporary=true&limit=3",
            status=200,
            body=json.dumps(mock_availabilities)
        )
        responses.add(
            responses.GET,
            "https://127.0.0.1/availabilities.json?start_date=2021-06-01&visit_motive_ids=2746983&agenda_ids=&insurance_sector=public&practice_ids=234567&destroy_temporary=true&limit=3",
            status=200,
            body=json.dumps(mock_availabilities)
        )

    mock_appointments = {
        "id": "appointment-id"
    }

    responses.add(
        responses.POST,
        "https://127.0.0.1/appointments.json",
        status=200,
        body=json.dumps(mock_appointments)
    )

    mock_appointments_edit = {
        "id": "appointment-edit-id",
        "appointment": {
            "custom_fields": {}
        }
    }

    responses.add(
        responses.GET,
        "https://127.0.0.1/appointments/appointment-id/edit.json",
        status=200,
        body=json.dumps(mock_appointments_edit)
    )

    responses.add(
        responses.GET,
        "https://127.0.0.1/second_shot_availabilities.json?start_date=2021-07-20&visit_motive_ids=2746983&agenda_ids=&first_slot=2021-06-10T08%3A40%3A00.000%2B02%3A00&insurance_sector=public&practice_ids=234567&limit=3",
        status=200,
        body=json.dumps(mock_availabilities)
    )

    mock_appointment_id_put = {
    }

    responses.add(
        responses.PUT,
        "https://127.0.0.1/appointments/appointment-id.json",
        status=200,
        body=json.dumps(mock_appointment_id_put)
    )

    mock_appointment_id = {
        "confirmed": True
    }

    responses.add(
        responses.GET,
        "https://127.0.0.1/appointments/appointment-id.json",
        status=200,
        body=json.dumps(mock_appointment_id)
    )

    result_handled = False
    for result in docto.find_centers(["Köln"]):
        result_handled = True

        center = result['search_result']

        # single shot vaccination
        assert docto.try_to_book(center=center,
                                 vaccine_list=["Janssen"],
                                 start_date=datetime.date(
                                     year=2021, month=6, day=1),
                                 end_date=datetime.date(
                                     year=2021, month=6, day=14),
                                 only_second=False,
                                 only_third=False,
                                 dry_run=False)
        assert len(responses.calls) == 10

        # two shot vaccination
        assert docto.try_to_book(center=center,
                                 vaccine_list=["Pfizer"],
                                 start_date=datetime.date(
                                     year=2021, month=6, day=1),
                                 end_date=datetime.date(
                                     year=2021, month=6, day=14),
                                 only_second=False,
                                 only_third=False,
                                 dry_run=False)
        assert len(responses.calls) == 20
        pass

    assert result_handled


@responses.activate
def test_find_motive_should_ignore_second_shot(tmp_path):
    """
    Check that find_motive ignores second shot motives
    """

    with open(FIXTURES_FOLDER + '/doctor_response.json') as json_file:
        mock_doctor_response = json.load(json_file)

    response = Response()
    response._content = b'{}'

    booking_page = CenterBookingPage(browser=Browser(), response=response)
    booking_page.doc = mock_doctor_response
    visit_motive_id = CenterBookingPage.find_motive(
        booking_page, '.*(Pfizer)', False)
    assert visit_motive_id == mock_doctor_response['data']['visit_motives'][1]['id']

    visit_motive_id = CenterBookingPage.find_motive(
        booking_page, '.*(Janssen)', True)
    assert visit_motive_id == mock_doctor_response['data']['visit_motives'][3]['id']

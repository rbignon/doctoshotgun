import pytest
import responses
from woob.browser.exceptions import ServerError
from doctoshotgun import DoctolibDE, DoctolibFR


@responses.activate
def test_find_centers_fr_returns_503_should_continue(tmp_path):
    """
    Check that find_centers doesn't raise a ServerError in case of 503 HTTP response
    """
    docto = DoctolibFR("roger.phillibert@gmail.com", "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/vaccination-covid-19/Paris?ref_visit_motive_ids%5B%5D=6970&ref_visit_motive_ids%5B%5D=7005&ref_visit_motive_ids%5B%5D=7945",
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
    docto = DoctolibDE("roger.phillibert@gmail.com", "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/impfung-covid-19-corona/M%C3%BCnchen?ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=7978",
        status=503
    )

    # this should not raise an exception
    for _ in docto.find_centers(["München"]):
        pass


@responses.activate
def test_find_centers_fr_returns_502_should_fail(tmp_path):
    """
    Check that find_centers raises an error in case of non-whitelisted status code
    """
    docto = DoctolibFR("roger.phillibert@gmail.com", "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/vaccination-covid-19/Paris?ref_visit_motive_ids%5B%5D=6970&ref_visit_motive_ids%5B%5D=7005&ref_visit_motive_ids%5B%5D=7945",
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
    docto = DoctolibDE("roger.phillibert@gmail.com", "1234", responses_dirname=tmp_path)
    docto.BASEURL = "https://127.0.0.1"

    responses.add(
        responses.GET,
        "https://127.0.0.1/impfung-covid-19-corona/M%C3%BCnchen?ref_visit_motive_ids%5B%5D=6768&ref_visit_motive_ids%5B%5D=6936&ref_visit_motive_ids%5B%5D=7978",
        status=502
    )

    # this should raise an exception
    with pytest.raises(ServerError):
        for _ in docto.find_centers(["München"]):
            pass

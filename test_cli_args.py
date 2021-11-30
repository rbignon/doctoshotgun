import responses
from unittest.mock import patch, MagicMock

from doctoshotgun import Application, DoctolibDE, DoctolibFR, MasterPatientPage

CENTERS = [
    {
        "name_with_title": "Doktor",
        "city": "koln",
    },
    {
        "name_with_title": "Doktor2",
        "city": "koln",
    },
    {
        "name_with_title": "Doktor",
        "city": "neuss",
    },
]


@responses.activate
@patch('doctoshotgun.DoctolibDE')
def test_center_arg_should_filter_centers(MockDoctolibDE, tmp_path):
    """
    Check that booking is performed in correct city
    """
    # prepare
    mock_doctolib_de = get_mocked_doctolib(MockDoctolibDE)

    # call
    center = 'Doktor'
    city = 'koln'
    call_application(city, cli_args=['--center', center])

    # assert
    assert mock_doctolib_de.get_patients.called
    assert mock_doctolib_de.try_to_book.called
    for call_args_list in mock_doctolib_de.try_to_book.call_args_list:
        assert call_args_list.args[0]['name_with_title'] == center
        assert call_args_list.args[0]['city'] == city


@responses.activate
@patch('doctoshotgun.DoctolibDE')
def test_center_exclude_arg_should_filter_excluded_centers(MockDoctolibDE, tmp_path):
    """
    Check that booking is performed in correct city
    """
    # prepare
    mock_doctolib_de = get_mocked_doctolib(MockDoctolibDE)

    # call
    excluded_center = 'Doktor'
    city = 'koln'
    call_application(city, cli_args=['--center-exclude', excluded_center])

    # assert
    assert mock_doctolib_de.get_patients.called
    assert mock_doctolib_de.try_to_book.called
    for call_args_list in mock_doctolib_de.try_to_book.call_args_list:
        assert call_args_list.args[0]['name_with_title'] != excluded_center
        assert call_args_list.args[0]['city'] == city


def get_mocked_doctolib(MockDoctolibDE):
    mock_doctolib_de = MagicMock(wraps=DoctolibDE)
    MockDoctolibDE.return_value = mock_doctolib_de

    mock_doctolib_de.vaccine_motives = DoctolibDE.vaccine_motives
    mock_doctolib_de.KEY_PFIZER = DoctolibDE.KEY_PFIZER
    mock_doctolib_de.KEY_MODERNA = DoctolibDE.KEY_MODERNA
    mock_doctolib_de.KEY_JANSSEN = DoctolibDE.KEY_JANSSEN

    mock_doctolib_de.get_patients.return_value = [
        {"first_name": 'First', "last_name": 'Name'}
    ]
    mock_doctolib_de.do_login.return_value = True

    mock_doctolib_de.find_centers.return_value = CENTERS

    mock_doctolib_de.try_to_book.return_value = True

    mock_doctolib_de.load_state.return_value = None
    mock_doctolib_de.dump_state.return_value = {}

    return mock_doctolib_de


def call_application(city, cli_args=[]):
    assert 0 == Application.main(
        Application(),
        cli_args=["de", city, "roger.phillibert@gmail.com", "1234"] + cli_args
    )

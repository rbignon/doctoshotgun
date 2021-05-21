# DOCTOSHOTGUN

This script lets you automatically book a vaccine slot on Doctolib for today or
tomorrow, following rules from the French Government.


## Python dependencies

- woob
- cloudscraper
- dateutil
- termcolor

## How to use it

Install dependencies:

```
pip install -r requirements.txt
```

Run:

```
./doctoshotgun.py <city> <email> [password]
```

For example:

```
$ ./doctoshotgun.py paris roger.philibert@gmail.com
Password:
::: Trying to find a slot in Centre de Vaccination Covid 19 - Ville de Paris
::: Best slot found: Mon May 17 11:00:00 2021
::: Second shot: Fri Jun 25 15:20:00 2021
::: Booking for Roger Philibert...
::: Booking status: True
::: Booked!
```

# Development

## Running tests

```
 $ pip install -r requirements-dev.txt
 $ pytest test_browser.py
```
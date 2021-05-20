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

### Arguments

`city`: The city name where you want to be vaccinated. To be more precise (if your city has several districts for instance), you can add the zip code before the city (for instance `75012-paris` or `69003-lyon`)

`email`: The email adress of your Doctolib account

`password` (optional): The password of your Doctolib account. If not specified, your password will be prompt at the launch of the script.


### Examples:

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

```
$ ./doctoshotgun.py 75012-paris philippe.edouard@gmail.com 'ThisIsNotAGoodPassword'
::: Trying to find a slot in Centre de vaccination COVID  Bauchat Paris 12
::: Looking for slots in place Centre de santé Bauchat Nation
::: No availabilities in this center
::: Fail, try next center...
::: Trying to find a slot in Centre de Vaccination Covid 19 - Ville de Paris
::: Looking for slots in place Centre de vaccination Aubrac
::: No availabilities in this center
::: Fail, try next center...
```

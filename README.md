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
./doctoshotgun.py --pro --debug <city> <email> [password]
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

If you don't set --pro it will avoid vaccination center within 'professionnel' in the place name

```
$ ./doctoshotgun.py --pro paris roger.philibert@gmail.com
Password:
[...]
::: Looking for slots in place Institut Cœur Poumon
::: First slot not found :(
::: Not looking for slots in place Centre de vaccination - Professionnels de santé et assimilés, as it's reserved for 'professionnel'
::: Fail, try next center...
[...]
```

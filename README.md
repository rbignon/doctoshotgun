# DOCTOSHOTGUN

This script lets you automatically book a vaccine slot on Doctolib in France and in Germany in
the next seven days.

<p align="center">
  <img src="https://github.com/rbignon/doctoshotgun/raw/master/example.svg">
</p>

## Python dependencies

- [woob](https://woob.tech)
- cloudscraper
- dateutil
- termcolor
- colorama
- playsound (optional)

## How to use it

You need python3 for this script. If you don't have it, please [install it first](https://www.python.org/).

Install dependencies:

```
pip install -r requirements.txt
```

Run:

```
./doctoshotgun.py <country{fr,de}> <city> <email> [<password>]
```

Further optional arguments:

```
--center "<name>" [--center <name> …] : filter centers to only choose one from the provided list
-p <index>, --patient <index>         : select patient for which book a slot
-z, --pfizer                          : looking only for a Pfizer vaccine
-m, --moderna                         : looking only for a Moderna vaccine
-j, --janssen                         : looking only for a Janssen vaccine
-d, --debug                           : display debug information
-t <days>, --time-window <days>       : set how many next days the script look for slots
--start-date <DD/MM/YYYY>             : first date on which you want to book the first slot
--end-date <DD/MM/YYYY>               : last date on which you want to book the first slot
--dry-run                             : do not really book a slot
```

### With Docker

Build the image:

```
docker build . -t doctoshotgun
```

Run the container:

```
docker run -it doctoshotgun <country{fr,de}> <city> <email> [<password>]
```

### Multiple cities

You can also look for slot in multiple cities at the same time. Cities must be separated by commas:

```
$ ./doctoshotgun.py <country{fr,de}> <city1>,<city2>,<city3> <email> [<password>]
```

### Filter on centers

You can give name of centers in which you want specifically looking for:

```
$ ./doctoshotgun.py fr paris roger.philibert@gmail.com \
      --center "Centre de Vaccination Covid 19 - Ville de Paris" \
      --center "Centre de Vaccination du 7eme arrondissement de Paris - Gymnase Camou"
```

### Select patient

For doctolib accounts with more thant one patient, you can select patient just after launching the script:

```
$ ./doctoshotgun.py fr paris roger.philibert@gmail.com PASSWORD
Available patients are:
* [0] Roger Philibert
* [1] Luce Philibert
For which patient do you want to book a slot?
```

You can also give the patient id as argument:

```
$ ./doctoshotgun.py fr paris roger.philibert@gmail.com PASSWORD -p 1
Starting to look for vaccine slots for Luce Philibert in 1 next day(s) starting today...
```

### Set time window

By default, the script looks for slots between now and next day at 23:59:59. If you belong to a category of patients that is allowed to book a slot in a more distant future, you can expand the time window. For exemple, if you want to search in the next 5 days :

```
$ ./doctoshotgun.py fr paris roger.philibert@gmail.com -t 5
Password:
Starting to look for vaccine slots for Roger Philibert in 5 next day(s) starting today...
This may take a few minutes/hours, be patient!
```

### Look on specific date

By default, the script looks for slots between now and next day at 23:59:59. If you can't be vaccinated right now (e.g covid in the last 3 months or out of town) and you are looking for an appointment in a distant future, you can pass a starting date:

```
$ ./doctoshotgun.py fr paris roger.philibert@gmail.com --start-date 17/06/2021
Password:
Starting to look for vaccine slots for Roger Philibert in 7 next day(s) starting 17/06/2021...
This may take a few minutes/hours, be patient!
```

### Filter by vaccine

The Pfizer vaccine is the only vaccine allowed in France for people between 16 and 18. For this case, you can use the -z option.

```
$ ./doctoshotgun.py fr paris roger.philibert@gmail.com PASSWORD -z
Starting to look for vaccine slots for Luce Philibert...
Vaccines: Pfizer
This may take a few minutes/hours, be patient!
```

It is also possible to filter on Moderna vaccine with the -m option and Janssen with the -j option.

## Development

### Running tests

```
 $ pip install -r requirements-dev.txt
 $ pytest test_browser.py
```

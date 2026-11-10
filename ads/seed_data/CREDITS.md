# Demo photo credits

The photos in `photos/` are used by `python manage.py seed_ads`. They come from
[Wikimedia Commons](https://commons.wikimedia.org/) and stay under their own licences, listed below.
Each copy here has been resized (at most 1000 px) and re-compressed as JPEG; that is the only change.
CC BY-SA photos are shared under the same licence.

| File | Original | Author | Licence |
|---|---|---|---|
| `camera-1.jpg` | [Sony Alpha7 III 20 apr 2018f](https://commons.wikimedia.org/wiki/File:Sony_Alpha7_III_20_apr_2018f.jpg) | 昼落ち | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `camera-2.jpg` | [Sony A 7 iii full frame mirrorless camera](https://commons.wikimedia.org/wiki/File:Sony_A_7_iii_full_frame_mirrorless_camera.jpg) | Amitabha Gupta | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `camera-3.jpg` | [Sony Alpha7 III 20 apr 2018d](https://commons.wikimedia.org/wiki/File:Sony_Alpha7_III_20_apr_2018d.jpg) | 昼落ち | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `prius-1.jpg` | [2015-2018 Toyota Prius S](https://commons.wikimedia.org/wiki/File:2015-2018_Toyota_Prius_S.jpg) | TTTNIS | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `prius-2.jpg` | [2015-2018 Toyota Prius S rear](https://commons.wikimedia.org/wiki/File:2015-2018_Toyota_Prius_S_rear.jpg) | TTTNIS | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `prius-3.jpg` | [Toyota Prius (XW50) Washington DC Metro Area, USA (1)](https://commons.wikimedia.org/wiki/File:Toyota_Prius_(XW50)_Washington_DC_Metro_Area,_USA_(1).jpg) | OWS Photography | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `apartment-1.jpg` | [Modern living room with stylish furniture and a view of the outdoors in a cozy apartment setting](https://commons.wikimedia.org/wiki/File:Modern_living_room_with_stylish_furniture_and_a_view_of_the_outdoors_in_a_cozy_apartment_setting.jpg) | Shixart1985 | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) |
| `apartment-2.jpg` | [Living room in apartment of Condomínio do Edifício Zaher, Le Blond, Rio de Janeiro, Brazil](https://commons.wikimedia.org/wiki/File:Living_room_in_apartment_of_Condom%C3%ADnio_do_Edif%C3%ADcio_Zaher,_Le_Blond,_Rio_de_Janeiro,_Brazil.jpg) | Wilfredor | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `apartment-3.jpg` | [The living room that needs houseplants](https://commons.wikimedia.org/wiki/File:The_living_room_that_needs_houseplants.jpg) | Lo (Flickr) | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `barista-1.jpg` | [Girl Making Espresso](https://commons.wikimedia.org/wiki/File:Girl_Making_Espresso.jpg) | Petteri Sulonen | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) |
| `barista-2.jpg` | [A barista carefully tamping espresso grounds at a busy street-side coffee stall](https://commons.wikimedia.org/wiki/File:DSC_9564_A_barista_carefully_tamping_espresso_grounds_at_a_busy_street-side_coffee_stall_preparing_fresh_coffee_for_customers.jpg) | PattayaPatrol | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `piano-1.jpg` | [Picture of piano lesson still under Covid-19 recovery time](https://commons.wikimedia.org/wiki/File:Picture_of_piano_lesson_still_under_Covid-19_recovery_time.jpg) | Jason M. C., Han | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `piano-2.jpg` | [Guna Goluba mūzika](https://commons.wikimedia.org/wiki/File:Guna_Goluba_m%C5%ABzika.jpg) | LVinRU | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `cat-1.jpg` | [Orange tabby cat sitting on fallen leaves-Hisashi-01A](https://commons.wikimedia.org/wiki/File:Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg) | Hisashi | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) |
| `cat-2.jpg` | [Orange tabby cat sitting on fallen leaves-Hisashi-01](https://commons.wikimedia.org/wiki/File:Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01.jpg) | Hisashi | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) |

When adding a demo photo, add it to `DEMO_ADS` in `ads/management/commands/seed_ads.py`
and to this table; a test checks that every bundled photo is credited here.

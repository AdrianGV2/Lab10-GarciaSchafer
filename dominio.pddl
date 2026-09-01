(define (domain manito-apilita-cubito)
    (:requirements :strips :typing)
    (:types
        cube
        zone
        )
    (:predicates
        (on ?cube1 - cube ?cube2 - cube)
        (at ?cube1 - cube ?zone1 - zone)
        (zone-free ?zone1 - zone)
        (holding ?cube1 - cube)
        (free-cube ?cube1 - cube)
        (manito-empty)
        )
    (:action grip
        :parameters (?cube1 - cube ?zone1 - zone)
        :precondition (and
            (free-cube ?cube1)
            (at ?cube1 ?zone1)
            (manito-empty))
        :effect (and
            (holding ?cube1)
            (zone-free ?zone1)
            (not (at ?cube1 ?zone1))
            (not (free-cube ?cube1))
            (not (manito-empty))
            )
        )
    (:action drop
        :parameters (?cube1 - cube ?zone1 - zone)
        :precondition (and
            (holding ?cube1)
            (zone-free ?zone1))
        :effect (and
            (at ?cube1 ?zone1)
            (free-cube ?cube1)
            (manito-empty)
            (not (zone-free ?zone1))
            (not (holding ?cube1)))
        )

    (:action stack
        :parameters (?cube1 - cube ?cube2 - cube)
        :precondition (and
            (holding ?cube1)
            (free-cube ?cube2))
        :effect (and
            (on ?cube1 ?cube2)
            (free-cube ?cube1)
            (manito-empty)
            (not (holding ?cube1))
            (not (free-cube ?cube2)))
        )

    (:action unstack
        :parameters (?cube1 - cube ?cube2 - cube)
        :precondition (and
            (on ?cube1 ?cube2)
            (free-cube ?cube1)
            (manito-empty))
        :effect (and
            (holding ?cube1)
            (free-cube ?cube2)
            (not (on ?cube1 ?cube2))
            (not (free-cube ?cube1))
            (not (manito-empty)))
        )
    )

(define (problem escenario1)
    (:domain manito-apilita-cubito)
    (:objects
        cubo-verde - cube
        zona-inicial - zone
        )
    (:init
        (at cubo-verde zona-inicial)
        (free-cube cubo-verde)
        (manito-empty)
        )
    (:goal
        (holding cubo-verde)
        )
    )

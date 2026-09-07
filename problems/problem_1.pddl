; Caso de calibracion: mover cubo-a a una zona libre y apilarlo sobre cubo-b.
; 4 objetos (2 cubos + 2 zonas), tal como exige la pauta.
(define (problem problem-1)
    (:domain manito-apilita-cubito)
    (:objects
        cubo-a cubo-b - cube
        zona-a zona-b - zone
        )
    (:init
        (at cubo-a zona-a)
        (at cubo-b zona-b)
        (free-cube cubo-a)
        (free-cube cubo-b)
        (manito-empty)
        )
    (:goal
        (on cubo-a cubo-b)
        )
    )

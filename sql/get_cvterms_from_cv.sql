SELECT cvterm.name as cvterm, cv.name as cv FROM cvterm JOIN cv ON cvterm.cv_id = cv.cv_id and cv.name in %(cvs)s
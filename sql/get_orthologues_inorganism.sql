SELECT 
    f.uniquename as feature, 
    orthof.uniquename as ortho,
    orthotype.name as orthotype,
    relationshiptype.name as relationshiptype,
    fcc.name as orthoproduct
FROM feature f
JOIN feature_relationship fr ON f.feature_id = fr.subject_id 
    AND fr.type_id in 
        (select cvterm.cvterm_id 
            from cvterm 
            join cv 
            on cvterm.cv_id = cvterm.cv_id 
            where cv.name = 'sequence' 
            and (cvterm.name = 'orthologous_to' or cvterm.name = 'paralogous_to'))
JOIN feature orthof ON fr.object_id = orthof.feature_id
JOIN cvterm orthotype ON orthof.type_id = orthotype.cvterm_id
JOIN cvterm relationshiptype ON fr.type_id = relationshiptype.cvterm_id

LEFT JOIN feature_cvterm fc ON fc.feature_id = orthof.feature_id
LEFT JOIN cvterm fcc ON fc.cvterm_id = fcc.cvterm_id 
LEFT JOIN cv fccc ON fccc.cv_id = fcc.cv_id AND fcc.name = 'genedb_products'

WHERE f.organism_id = %(organism_id)s

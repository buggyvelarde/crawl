SELECT 
    src.uniquename as sourcefeature, 
    substr(src.residues, fl.fmin, fl.fmax) AS residues,
    f.uniquename as feature
FROM feature src 
JOIN featureloc fl ON src.feature_id = fl.srcfeature_id
JOIN feature f ON fl.feature_id = f.feature_id AND f.uniquename IN %(genes)s
WHERE src.uniquename = %(sourcefeature)s
AND f.type_id IN (792, 423)

;
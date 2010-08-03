SELECT feature.uniquename as feature, synonym.name as synonym, cvterm.name as type
FROM feature_synonym 
JOIN feature ON feature.feature_id = feature_synonym.feature_id 
JOIN synonym ON feature_synonym.synonym_id = synonym.synonym_id
JOIN cvterm ON synonym.type_id = cvterm.cvterm_id
where feature.uniquename in %(uniquenames)s 
UNION
SELECT feature.uniquename as feature, synonym.name as synonym, cvterm.name as type
FROM feature_synonym 
JOIN feature ON feature.feature_id = feature_synonym.feature_id 
JOIN synonym ON feature_synonym.synonym_id = synonym.synonym_id
JOIN cvterm ON synonym.type_id = cvterm.cvterm_id
where synonym.name in %(uniquenames)s


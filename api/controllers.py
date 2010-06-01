#!/usr/bin/env python
# encoding: utf-8
"""
controllers.py

Classes in this module are for exposure as web or command line services. They inherit from ropy.server.RESTController, and their methods are 
decorated to expose them. 

Created by Giles Velarde on 2010-02-04.
Copyright (c) 2010 Wellcome Trust Sanger Institute. All rights reserved.
"""

import os
import cherrypy
import logging

logger = logging.getLogger("crawl")

import ropy.server
import db

from userplot.parser.wiggle import Wiggles, Track, WiggleException

class BaseController(ropy.server.RESTController):
    """
        An abstract class with common methods shared by crawl controllers. Not to be instantiated directly.
    """
   
    def __init__(self):
        self.templateFilePath = os.path.dirname(__file__) + "/../tpl/"
        
        # declaring an instance variable, which will be called by most methods, must set if the controller is instantiated out of a server context
        # designed to be a db.Queries instance
        self.queries = None
        
    
    def init_handler(self):
        self.queries = db.Queries(cherrypy.thread_data.connectionFactory)
        #self.api = api.API(cherrypy.thread_data.connectionFactory)
        super(BaseController, self).init_handler()
    
    def _get_relationship_ids(self, relationships):
        relationship_ids = []
        
        """
            part_of is currently stored in a different CV term to the rest :
            select count(type_id), cvterm.name, cv.name from feature_relationship join cvterm on feature_relationship.type_id = cvterm.cvterm_id join cv on cvterm.cv_id = cv.cv_id group by cvterm.name, cv.name;
              count  |      name      |     name     
            ---------+----------------+--------------
              510619 | derives_from   | sequence
              406534 | orthologous_to | sequence
                 341 | paralogous_to  | sequence
             1929818 | part_of        | relationship
            
            so we need to make sure that its cvterm_id is fetched from the right cv!
        """
        if "part_of" in relationships:
            relationships.remove("part_of")
            relationship_ids = self.queries.getCvtermID("sequence", relationships)
            part_of_id = self.queries.getCvtermID("relationship", ["part_of"])[0]
            relationship_ids.append(part_of_id)
        else:
            relationship_ids = self.queries.getCvtermID("sequence", relationships)
        return relationship_ids

    def _getGenesWithHistoryChanges(self, organism_id, since):

        cvterm_infos = self._getHistoryCvtermPropTypeIDs()

        qualifier_type_id = cvterm_infos[0]["id"]
        curatorName_type_id = cvterm_infos[1]["id"]
        date_type_id = cvterm_infos[2]["id"]

        results = self.queries.getGenesWithHistoryChanges(organism_id, since, date_type_id, curatorName_type_id, qualifier_type_id)

        return results
    
    def _getHistoryCvtermPropTypeIDs(self):
        cvterm_infos = (
            { "cv" : "genedb_misc",         "cvterm" : "qualifier" }, 
            { "cv" : "genedb_misc",         "cvterm" : "curatorName" }, 
            { "cv" : "feature_property",    "cvterm" : "date" }
        )

        for cvterm_info in cvterm_infos:
            cvterm_info["id"] = self.queries.getCvtermID( cvterm_info["cv"], [cvterm_info["cvterm"]] )[0]

        return cvterm_infos
    
    def _sql_results_to_collection(self, key, collection_name, results):
        
        hash_store = {}
        collection = []
        
        for result in results:
            if key not in result: 
                raise ropy.server.ServerException("Could not parse the result because it does not have the %s key" % key, ropy.server.ERROR_CODES["DATA_PARSING_ERROR"])
            
            result_key_value = result[key]
            del result[key]
            
            if result_key_value not in hash_store:
                hash_store[result_key_value] = {
                    key : result_key_value,
                    collection_name : []
                }
                collection.append(hash_store[result_key_value])
            
            hash_store[result_key_value][collection_name].append(result)
        
        hash_store = None
        return collection

        
class Histories(BaseController):
    """History related queries"""
    
    @cherrypy.expose
    @ropy.server.service_format("history_annotations")
    def annotation_changes(self, taxonomyID, since):
        """Returns a list of genes that have been detected to have annotation changes."""
        
        organism_id = self.queries.getOrganismFromTaxon(taxonomyID)
        
        cvterm_infos = self._getHistoryCvtermPropTypeIDs()

        qualifier_type_id = cvterm_infos[0]["id"]
        curatorName_type_id = cvterm_infos[1]["id"]
        date_type_id = cvterm_infos[2]["id"]

        rows = self.queries.getGenesWithHistoryChangesAnywhere(organism_id, since, date_type_id, curatorName_type_id, qualifier_type_id)
        
        serving = ropy.server.serving
        
        results = []
        for row in rows:
            
            result = {
                "type" : row["type"],
                "feature_type" : row["ftype"],
                "feature" : row["f"],
                "change" : row["changedetail"],
                "date" : row["changedate"]
            }
            
            # do not show the user if the server is serving, i.e. if this is a webservice
            if serving == False :
                result["user"] = row["changeuser"]
            else:
                result["user"] = "---"
                
            fs = (row["f"], row["f2"], row["f3"])
            ftypes = (row["ftype"], row["ftype2"], row["ftype3"])
            for i in range(len(ftypes)):
                ftype = ftypes[i]
                if ftype == "gene" or ftype == "pseudogene":
                    result["gene"] = fs[i]
            
            results.append(result)
        
        data = {
            "response" : {
                "name" : "genes/annotation_changes",
                "taxonomyID" : taxonomyID,
                "count" : len(results),
                "since" : since,
                "results" : results
            }
        }
        
        return data
    
    annotation_changes.arguments = { 
        "since" : "date formatted as YYYY-MM-DD", 
        "taxonomyID" : "the NCBI taxonomy ID" 
    }
        
    
class Genes(BaseController):
    """
        Gene related queries.
    """
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def inorganism(self, taxonID):
        """
            Returns a list of genes in an organism.
        """
        organism_id = self.queries.getOrganismFromTaxon(taxonID)
        results = self.queries.getCDSs(organism_id)
        data = {
            "response" : {
                "name" : "genes/list",
                "genes" : results
            }
        }
        return data
        #return self.api.getCDSs(taxonID)
    inorganism.arguments = {
        "taxonID" : "the taxonID of the organism you wish to obtain genes from"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def inregion(self, region):
        """
            Returns a list of genes located on a particular source feature (e.g. a contig).
        """
        genes = self.queries.getGenes(region)
        data = {
            "response" : {
                "name" : "genes/inregion",
                "genes" : genes
            }
        }
        return data
    inregion.arguments = {
        "region" : "the name of a region, i.e. one of the entries returned by /top.",
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def sequence(self, region, genes = []):
        """
            Returns a list of genes located on a particular region (e.g. a contig), with their sequences extracted from that region.
        """
        genes = ropy.server.to_array(genes)
        sequence = self.queries.getGeneSequence(region, genes)
        data = {
            "response" : {
                "name" : "genes/sequence",
                "sequence" : sequence
            }
        }
        return data
    sequence.arguments = {
        "region" : "the name of a region, i.e. one of the entries returned by /top.",
        "genes" : "a list of genes, for instance as supplied by the /inregion or /inorganism queries."
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def mrnasequence(self, genes):
        """
            Returns a mRNA sequences for a list of genes.
        """
        genes = ropy.server.to_array(genes)
        results = self.queries.getMRNAs(genes)
        data = {
            "response" : {
                "name" : "genes/mrnasequence",
                "mrnas" : results
            }
        }
        return data
    mrnasequence.arguments = {
        "genes" : "a list of genes"
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def polypeptidesequence(self, genes):
        """
            Returns a polypeptide sequences for a list of genes.
        """
        genes = ropy.server.to_array(genes)
        #genenames = ropy.server.get_array_from_hash("genenames", kwargs)
        results = self.queries.getPEPs(genes)
        data = {
            "response" : {
                "name" : "genes/polypeptidesequence",
                "polypeptides" : results
            }
        }
        return data
    polypeptidesequence.arguments = {
        "genes" : "a list of genes"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def exons(self, region, genes = []):
        """
           Returns the exons coordinates for a list of genes.
        """
        genes = ropy.server.to_array(genes)
        results = self.queries.getExons(region, genes)
        data = {
            "response" : {
                "name" :"genes/exons",
                "coordinates" : results
            }
        }
        return data
    exons.arguments = {
        "region" : "the region upon which the genes are located", 
        "genes": "the gene features" 
    }
    
    
    
    @cherrypy.expose
    @ropy.server.service_format("changes")
    def changes(self, since, taxonomyID):
        """
            Reports all the features that have changed since a certain date.
        """
        organism_id = self.queries.getOrganismFromTaxon(taxonomyID)
        changed_features = self.queries.getAllChangedFeaturesForOrganism(since, organism_id)
        data = {
            "response" : {
                "name" : "genes/changes",
                "taxonID" : taxonomyID,
                "count" : len(changed_features),
                "since" : since,
                "results" : changed_features
            }
        }
        #data = self.api.gene_changes(since, taxonomyID)
        return data
    
    changes.arguments = { 
        "since" : "date formatted as YYYY-MM-DD", 
        "taxonomyID" : "the NCBI taxonomy ID"  
    }
    
    @cherrypy.expose
    @ropy.server.service_format("private_annotations")
    def annotation_changes(self, taxonomyID, since):
        """
            Reports all the genes that have been highlighted as having annotation changes.
        """
        organism_id = self.queries.getOrganismFromTaxon(taxonomyID)
        # print organism_id
        rows = self.queries.getGenesWithPrivateAnnotationChanges(organism_id, since)
        
        # bring in the new style changes
        # eventually, once all the privates have been migrated, we can remove the query above
        rows_history = self._getGenesWithHistoryChanges(organism_id, since)
        for row_history in rows_history:
            rows.append(row_history)
        
        data = {
            "response" : {
                "name" : "genes/annotation_changes",
                "taxonomyID" : taxonomyID,
                "count" : len(rows),
                "since" : since,
                "results" : rows
            }
        }
        #data = self.api.annotation_changes(taxonomyID, since)
        return data
    
    annotation_changes.arguments = { 
        "since" : "date formatted as YYYY-MM-DD", 
        "taxonomyID" : "the NCBI taxonomy ID" 
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def domains(self, genes):
        """
           Returns domains associated with particular genes.
        """
        genes = ropy.server.to_array(genes)
        relationship_ids = self._get_relationship_ids(["derives_from", "part_of"])
        results = self.queries.getDomains(genes, relationship_ids)
        data = {
            "response" : {
                "name" : "genes/domains",
                "results" : results
            }
        }
        return data
    domains.arguments = {
        "genes" : "a list of gene names you want to search for domains"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def withdomains(self, domains):
        """
           Returns genes associated with particular domains.
        """
        domains = ropy.server.to_array(domains)
        relationship_ids = self._get_relationship_ids(["derives_from", "part_of"])
        results = self.queries.getWithDomains(domains, relationship_ids)
        data = {
            "response" : {
                "name" : "genes/withdomains",
                "results" : results
            }
        }
        return data
    domains.arguments = {
        "domains" : "a list of domain names you want genes for"
    }
    
    
    
    
    
    
#    @cherrypy.expose
#    @ropy.server.service_format()
#    def annotationchangecvterms(self):
#        """
#           Returns the members of the controlled vocabulary used to type biologically meaningful annotation changes.
#        """
#        data = {
#            "response" : {
#                "name" :"genes/annotationchangecvterms",
#                "coordinates" : self.queries.getAnnotationChangeCvterms()
#            }
#        }
#        return data
#    annotationchangecvterms.arguments = {}


class Features(BaseController):
    """
        Feature related queries.
    """
    
    @cherrypy.expose
    @ropy.server.service_format()
    def properties(self, features = [], uniqueNames=[], u=[], us=None, delimiter = ","):
        """
            Returns featureprops for a given set of uniqueNames.
        """
        
        # build the uniqueNames array from different possilble kwargs
        uniqueNames = ropy.server.to_array(uniqueNames) 
        
        features = ropy.server.to_array(features)
        if len(features) > 0: uniqueNames.extend(features)
        
        u = ropy.server.to_array(u)
        if len(u) > 0: uniqueNames.extend(u)
        
        # special case of arrays being passed using the us parameter, with the delimiter
        if us != None: uniqueNames.extend(us.split(delimiter))
        
        logger.debug(uniqueNames)
        
        if len(uniqueNames) == 0: 
            raise ropy.server.ServerException("Please provide at least one  uniqueName using either the uniqueNames, u or us parameters.", ropy.server.ERROR_CODES["MISSING_PARAMETER"])
        
        
        results = self._sql_results_to_collection("feature", "props", self.queries.getFeatureProps(uniqueNames))
        
        # prop_dict = {}
        #         prop_list = []
        #         
        #         for r in results:
        #             uniquename = r.pop("uniquename")
        #             
        #             if uniquename not in prop_dict:
        #                 prop_dict[uniquename] = {
        #                     "uniquename" : uniquename,
        #                     "props" : []
        #                 }
        #                 prop_list.append(prop_dict[uniquename])
        #             
        #             this_feature_prop = prop_dict[uniquename]
        #             this_feature_prop["props"].append(r)
        #             
        #         
        #         prop_dict = None
        
        data = {
            "response" : {
                "name" : "features/properties",
                "features" : results
            }
        }
        return data
    
    properties.arguments = {
        "features" : "the uniqueName of the feature whose properties you're after",
        "uniqueName" : "the uniqueName of the feature whose properties you're after",
        "u" : "shorthand for the uniqueName parameter",
        "us" : "a single string making up a list of uniqueNames, delimited by the delimiter parameter",
        "delimiter" : "instructs how to split strings, defaults to a comma(,)"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def length(self, uniquename):
        """
            Returns the length of a feature.
        """
        
        results = self.queries.getFeatureLength(uniquename)
        
        if results == 0:
            coordinates = self.queries.getFeatureCoordinates([uniquename], None)
            if len(coordinates) > 0:
                for coordinate in coordinates:
                    length = int(coordinate["fmax"]) - int(coordinate["fmin"])
                    coordinate["length"] = str(length)
                results = coordinates
            
        
        data = {
            "response" : {
                "name" :"genes/length",
                "uniquename" : uniquename,
                "length" : results
            }
        }
        return data
        #return self.api.getFeatureLength(uniquename)
    length.arguments = { "uniquename" : "the uniquename of the feature" }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def orthologues(self, features):
        """
           Returns orthologues for a list of features.
        """
        
        features = ropy.server.to_array(features)
        results = self.queries.getOrthologues(features)
        
        orthologues = []
        ortho_store = {}
        for result in results:
            feature = result["feature"]
            #delete result["feature"]
            if feature not in ortho_store:
                ortho_store[feature] = {
                    "feature" : feature,
                    "orthologues" : []
                }
                orthologues.append(ortho_store[feature])
            ortho_store[feature]["orthologues"].append(result)
        
        ortho_store = None
        
        data = {
            "response" : {
                "name" : "features/orthologues",
                "features" : orthologues
            }
        }
        return data
    orthologues.arguments = {
        "features" : "the features"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def orthologuesinorganism(self, taxonID):
        """
           Gets all the orthologues in an organism.
        """
        organism_id = self.queries.getOrganismFromTaxon(taxonID)
        results = self.queries.getOrthologuesInOrganism(organism_id)
        return ({
            "response" : {
                "name" : "features/orthologuesinorganism",
                "orthologues" : results
            }
        })
    orthologuesinorganism.arguments = {
        "taxonID" : "the organism's taxonID"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def clusters(self, orthologues):
        """
           Returns a the orthologue clusters for a given set of orthologues. 
        """
        orthologues = ropy.server.to_array(orthologues)
        results = self.queries.getOrthologueClusters(orthologues)
        
        data = []
        store = {}
        for result in results:
            cluster_name = result["cluster_name"]
            del result["cluster_name"]
            if cluster_name not in store:
                store[cluster_name] = []
                data.append({
                    "cluster_name" : cluster_name,
                    "cluster" : store[cluster_name]
                })
            store[cluster_name].append(result)
        store = None
        return ({
            "response" : {
                "name" : "features/clusters",
                "clusters" : data
            }
        })
    clusters.arguments = {
        "orthologues" : "the orthologues"
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def coordinates(self, features, region = None):
        
        features = ropy.server.to_array(features)
        results = self._sql_results_to_collection("feature", "regions", self.queries.getFeatureCoordinates(features, region))
        
        data = {
            "response" : {
                "name" :"features/coordinates",
                "coordinates" : results
            }
        }
        return data
    coordinates.arguments = {
        "features": "the features" ,
        "region" : "the region upon which the features are located (optional, if not supplied it should fetch all locations)" 
    }
    
    
    def _parse_feature_cvterms(self, results):
        to_return = []
        feature_store = {}
        cvterm_store = {}
        
        for result in results:
            if result["feature"] not in feature_store:
                feature_store[result["feature"]] =  {
                    "feature" : result["feature"],
                    "terms" : []
                }
                to_return.append (feature_store[result["feature"]])
                
            if result["cv"] != None:
                cvterm_store_key = result["feature"] + result["cvterm"]
                
                if cvterm_store_key not in cvterm_store:
                    cvterm_store[cvterm_store_key] = {
                        "cvterm" : result["cvterm"],
                        "cv" : result["cv"],
                        "is_not" : result["is_not"],
                        "accession" : result["accession"],
                        "props" : [],
                        "pubs": self.queries.getFeatureCVTermPub(result["feature_cvterm_id"]),
                        "dbxrefs" : self.queries.getFeatureCVTermDbxrefs(result["feature_cvterm_id"])
                    }
                    
                    
                    feature_store[result["feature"]]["terms"].append(cvterm_store[cvterm_store_key])
                
                if "prop" in result and result["prop"] != "None":
                    cvterm_store[cvterm_store_key]["props"].append ({
                        "prop" : result["prop"],
                        "proptype" : result["proptype"],
                        "proptypecv" : result["proptypecv"]
                    })
            
        feature_store = None
        cvterm_store = None
        return to_return
    
    @cherrypy.expose
    @ropy.server.service_format()
    def terms(self, features, controlled_vocabularies = []):
        """
            Returns cvterms of type cv_names associated with list of features.
        """
        
        features = ropy.server.to_array(features)
        controlled_vocabularies = ropy.server.to_array(controlled_vocabularies)
        
        logger.debug(features)
        logger.debug(controlled_vocabularies)
        
        results = self._parse_feature_cvterms(self.queries.getFeatureCVTerm(features, controlled_vocabularies))
        
        data = {
            "response" : {
                "name" :"features/terms",
                "features" : results
            }
        }
        return data
    terms.arguments = { 
        "features" : "the uniquenames of the features", 
        "controlled_vocabularies": "the names of the controlled vocabularies" 
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def withterm(self, term, controlled_vocabulary):
        results = self.queries.getFeatureWithCVTerm(term, controlled_vocabulary)
        
        for result in results:
            term_properties = result["term_properties"]
            term_property_types = result["term_property_types"]
            term_property_type_vocabularies = result["term_property_type_vocabularies"]
            
            del result["term_properties"]
            del result["term_property_types"]
            del result["term_property_type_vocabularies"]
            
            properties = []
            
            for i in range(len(term_properties)):
                properties.append({
                    "value" : term_properties[i],
                    "type" : term_property_types[i],
                    "cv" : term_property_type_vocabularies[i]
                })
             
            result["properties"] = properties
        
        
        data = {
            "response" : {
                "name" :"features/withterm",
                "features" : results
            }
        }
        return data
    withterm.arguments = { "term" : "the controlled vocabulary term", "controlled_vocuabulary" : "the controlled vocabulary name" }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def withproperty(self, type, value, regex = False):
        logger.debug(regex)
        regex = ropy.server.to_bool(regex)
        logger.debug(regex)
        results = self.queries.getFeatureWithProp(type, value, regex)
        data = {
            "response" : {
                "name" :"features/withproperty",
                "features" : results
            }
        }
        return data
    withproperty.arguments = { "type" : "the type of property", "value" : "the value of the property", "regex" : "whether or not to search the values by POSIX regex (default False)" }
        
    
    @cherrypy.expose
    @ropy.server.service_format()
    def featuresequenceonregion(self, region, features):
        """
            Returns the sequences of features mapped onto a region.
        """
        features = ropy.server.to_array(features)
        # logger.debug(features)
        results = self.queries.getFeatureSequenceFromRegion(region, features)
        data = {
            "response" : {
                "name" : "features/featuresequenceonregion",
                "sequence" : results
            }
        }
        return data
    featuresequenceonregion.arguments = {
        "region" : "the region upon which you want to get the features",
        "features" : "a list of features whose sequences you wish to retrieve, located on the region"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def summary(self, features):
        """
           A summary of a feature.
        """
        
        features = ropy.server.to_array(features)
        
        featureproperties = self._sql_results_to_collection("feature", "props",self.queries.getFeatureProps(features))
        terms = self._parse_feature_cvterms(self.queries.getFeatureCVTerm(features, []))
        featurecoordinates = self._sql_results_to_collection("feature", "regions", self.queries.getFeatureCoordinates(features))
        
        pubs = self._sql_results_to_collection("feature", "pubs", self.queries.getFeaturePub(features))
        dbxrefs = self._sql_results_to_collection("feature", "dbxrefs", self.queries.getFeatureDbxrefs(features))
        
        relationship_ids = self._get_relationship_ids(["derives_from", "part_of"])
        relationship_results = self._sql_results_to_collection("feature", "relations", self.queries.getRelationships(features, relationship_ids))
        
        return {
            "response" : {
                "name" : "features/summary",
                "coordinates" : featurecoordinates,
                "properties" : featureproperties,
                "terms" : terms,
                "pubs" : pubs,
                "dbxrefs" : dbxrefs,
                "relationships" : relationship_results
            }
        }
        
    summary.arguments = {
        "features" : "a list of features whose sequences you wish to retrieve"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def relationships(self, features, relationships = ["derives_from", "part_of"]):
        """
           Gets the relationships of a feature.
        """
        
        features = ropy.server.to_array(features)
        relationships = ropy.server.to_array(relationships)
        
        relationship_ids = self._get_relationship_ids(relationships)
        
        results = self._sql_results_to_collection("feature", "relations", self.queries.getRelationships(features, relationship_ids))
        
        return {
            "response" : {
                "name" : "features/relationships",
                "results" : results
            }
        }
        
    relationships.arguments = {
        "features" : "a list of features whose sequences you wish to retrieve",
        "relationships" : "an optional array (i.e. it can be specified several times) detailing the relationship types you want to have, the defaults are [part_of, derives_from]"
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def pubs(self, features):
        """
           Gets the pubs of a feature.
        """
        
        features = ropy.server.to_array(features)
        results = self._sql_results_to_collection("feature", "pubs", self.queries.getFeaturePub(features))
        
        return {
            "response" : {
                "name" : "features/pubs",
                "features" : results
            }
        }
        
    pubs.arguments = {
        "features" : "a list of features",
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def dbxrefs(self, features):
        """
           Gets the dbxrefs of a feature.
        """
        
        features = ropy.server.to_array(features)
        results = self._sql_results_to_collection("feature", "dbxrefs", self.queries.getFeatureDbxrefs(features))
        
        return {
            "response" : {
                "name" : "features/dbxrefs",
                "features" : results
            }
        }
        
    dbxrefs.arguments = {
        "features" : "a list of features",
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def withnamelike(self, term):
        """
           Returns features with names like the search term.
        """
        return {
            "response" : {
                "name" : "features/dbxrefs",
                "features" : self.queries.getFeatureWithNameLike(term)
            }
        }
        
    withnamelike.arguments = {
        "features" : "a list of features",
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def analyses(self, features):
        """
           Returns any analyses associated with a feature.
        """
        features = ropy.server.to_array(features)
        results = self._sql_results_to_collection("feature", "analyses", self.queries.getAnlysis(features))
        return {
            "response" : {
                "name" : "features/analyses",
                "features" : results
            }
        }
    
    withnamelike.arguments = {
        "features" : "a list of features",
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def blast(self, subject, start, end, target = None, score = None):
        """
           Returns any blast matches linked to a subject and a target.
        """
        matches = self.queries.getBlastMatch(subject, start, end, target, score)
        results = {
            "response" : {
                "name" : "features/blast",
                "subject" : subject, 
                "start" : start,
                "end" : end, 
                "count" : len(matches),
                "matches" : matches
            }
        }
        if target is not None: results["response"]["target"] = target
        if score is not None: results["response"]["score"] = score
        return results
    blast.arguments = {
        "subject" : "the subject feature",
        "start" : "the start coordinate",
        "end" : "the end coordinate",
        "target" : "the target feature (optional)", 
        "score" : "the score (optional)"
    }
    

class Graphs(BaseController):
    """
       Plots plots.
    """
    
    def _get_graph(self, id):
        if hasattr(self, "graphs") == False:
            self.graphs = {}
        sid = str(id)
        if sid not in self.graphs:
            result = self.queries.getGraphData(sid)
            wiggles = Wiggles(result["data"])
            self.graphs[sid] = wiggles
        return self.graphs[sid]
    
    @cherrypy.expose
    @ropy.server.service_format()
    def list(self):
        """
           Returns a list of all the graphs in the database.
        """
        return {
            "response" : {
                "name" : "graphs/list",
                "plots" : self.queries.getGraphList()
            }
        }
    list.arguments = { }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def data(self, id):
        """
           Returns the entire graph data.
        """
        
        wiggles = self._get_graph(id)
        
        tracks = []
        
        for browser in wiggles.browser:
            tracks.append(browser)
        
        for track in wiggles.tracks:
            tracks.append(str(track))
        
        return {
            "response" : {
                "name" : "graphs/data",
                "graph" : "\n".join(tracks)
            }
        }
    data.arguments = { "id" : "the id of the graph" }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def info(self, id):
        """
           Returns the information about a graph.
        """
        
        wiggles = self._get_graph(id)
        
        tracks = {}
        tracks["browser"] = wiggles.browser
        tracks["tracks"] = []
        
        for track in wiggles.tracks:
            tracks["tracks"].append({
                "info" : track.info()
            })
        
        return {
            "response" : {
                "name" : "graphs/data",
                "graph" : tracks
            }
        }
    data.arguments = { "id" : "the id of the graph" }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def fixed(self, id, step, span, start, end, format=False):
        """
           Returns the plot data in fixed-step format.
        """
        
        wiggles = self._get_graph(id)
        format = ropy.server.to_bool(format)
        tracks = []
        
        for track in wiggles.tracks:
            
            if format:
                tracks.append(track._format_fixed(step, span, start, end))
            else:
                tracks.append({
                    "info" : track.info(),
                    "data" : track.fixed(step, span, start, end)
                })
        
        return {
            "response" : {
                "name" : "plots/fixed",
                "tracks" : tracks
            }
        }
    fixed.arguments = { 
        "id" : "the id of the graph",
        "step" : "the desired step size (optional - defaults to whatever is in the file)",
        "span" : "the desired span size (optional - defaults to whatever is in the file)",
        "start" : "the start point window (optional - defaults to the start of the data)",
        "end" : "the end point window (optional - defaults to the end of the data plus the span)",
        "format" : "if true, will return the data as a wiggle track string inside the json, if false, will serialise it to json"
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def fixed_scaled(self, id, step , span, start, end, format=False, minimum = 0, maximum = 1):
        """
           Returns the plot data in fixed-step format, scaled between the minimum and maximum parameters.
        """
        
        wiggles = self._get_graph(id)
        format = ropy.server.to_bool(format)
        tracks = []
        
        for track in wiggles.tracks:
            
            # make a new track that is scaled
            track = track.scale(minimum, maximum)
            
            if format:
                tracks.append(track._format_fixed(step, span, start, end))
            else:
                tracks.append({
                    "info" : track.info(),
                    "data" : track.fixed(step, span, start, end)
                })
        
        return {
            "response" : {
                "name" : "plots/fixed",
                "tracks" : tracks
            }
        }
    fixed_scaled.arguments = { 
        "id" : "the id of the graph",
        "step" : "the desired step size (optional - defaults to whatever is in the file)",
        "span" : "the desired span size (optional - defaults to whatever is in the file)",
        "start" : "the start point window (optional - defaults to the start of the data)",
        "end" : "the end point window (optional - defaults to the end of the data plus the span)",
        "format" : "if true, will return the data as a wiggle track string inside the json, if false, will serialise it to json",
        "minimum" : "the bottom value of the scale",
        "maximum" : "the top value of the scale"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def variable(self, id, steps, span = None, format=False):
        """
           Returns the plot data in variable-step format.
        """
        
        steps = ropy.server.to_array(steps)
        
        wiggles = self._get_graph(id)
        tracks = []
        for track in wiggles.tracks:
            if format:
                tracks.append(track._format_variable(steps, span))
            else:
                tracks.append({
                    "info" : track.info(),
                    "data" : track.variable(steps, span)
                })
        
        return {
            "response" : {
                "name" : "plots/fixed",
                "tracks" : tracks
            }
        }
    variable.arguments = { 
        "id" : "the id of the graph",
        "steps" : "an array of steps that you want list",
        "span" : "the desired span size (optional - defaults to whatever is in the file)",
        "format" : "if true, will return the data as a wiggle track string inside the json, if false, will serialise it to json"
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def variable_scaled(self, id, steps, span = None, format=False, minimum = 0, maximum = 1):
        """
           Returns the plot data in variable-step format, scaled between the minimum and maximum parameters.
        """
        
        steps = ropy.server.to_array(steps)
        
        wiggles = self._get_graph(id)
        tracks = []
        for track in wiggles.tracks:
            
            # make a new track that is scaled
            track = track.scale(minimum, maximum)
            
            if format:
                tracks.append(track._format_variable(steps, span))
            else:
                tracks.append({
                    "info" : track.info(),
                    "data" : track.variable(steps, span)
                })
        
        return {
            "response" : {
                "name" : "plots/fixed",
                "tracks" : tracks
            }
        }
    variable_scaled.arguments = { 
        "id" : "the id of the graph",
        "steps" : "an array of steps that you want list",
        "span" : "the desired span size (optional - defaults to whatever is in the file)",
        "format" : "if true, will return the data as a wiggle track string inside the json, if false, will serialise it to json",
        "minimum" : "the bottom value of the scale",
        "maximum" : "the top value of the scale"
    }
    


class Terms(BaseController):
    """
        Controlled vocabulary related queries.
    """
    
    @cherrypy.expose
    @ropy.server.service_format()
    def vocabularies(self):
        """
           Gets a list of all the controlled vocabularies in the database.
        """
        
        
        results = self.queries.getCV()
        
        return {
            "response" : {
                "name" : "terms/vocabularies",
                "results" : results
            }
        }
    vocabularies.arguments = {}
    
    @cherrypy.expose
    @ropy.server.service_format()
    def list(self, vocabularies):
        """
           Gets a list of all the terms in specified controlled vocabularies.
        """
        
        vocabularies = ropy.server.to_array(vocabularies)
        results = self.queries.getCvterms(vocabularies)
        
        return {
            "response" : {
                "name" : "terms/list",
                "results" : results
            }
        }
        
    list.arguments = {
        "vocabularies" : "the controlled vocabularies you want to extract terms from"
    }

class Regions(BaseController):
    """
        Source feature related queries.
    """
    @cherrypy.expose
    @ropy.server.service_format()
    def sequence(self, uniqueName, start, end):
        """
            Returns the sequence of a source feature.
        """
        rows = self.queries.getRegionSequence(uniqueName)
        row = rows[0]

        length = row["length"]
        dna = row["dna"]
        dna = dna[int(start)-1:int(end)-1]

        data = {
            "response" : {
                "name" : "regions/sequence",
                "sequence" :  [{
                    "uniqueName" : uniqueName,
                    "start" : start,
                    "end" : end,
                    "length" : length,
                    "dna" : dna,
                    "organism_id" : row["organism_id"]
                }]
            }
        }
        return data
    
    sequence.arguments = { 
        "uniqueName" : "the uniqueName of the source feature" ,
        "start" : "the start position in the sequence that you wish to retrieve (counting from 1)",
        "end" : "the end position in the sequence that you wish to retrieve (counting from 1)"
    }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def featureloc(self, uniqueName, start, end, relationships = [], flattened=False):
        """
            Returns information about all the features located on a source feature within min and max boundaries.
        """
        
        flattened = ropy.server.to_bool(flattened)
        relationships = ropy.server.to_array(relationships)
        
        if len(relationships) == 0: 
            relationships = ["part_of", "derives_from"]
        
        logger.debug(relationships)
        logger.debug(uniqueName + " : " + str(start) + " - " + str(end))
        
        regionID = self.queries.getFeatureID(uniqueName)
        
        relationship_ids = self._get_relationship_ids(relationships)
        
        if len(relationship_ids) == 0:
            raise ropy.server.ServerException("Could not find any cvterms " + str(relationships) + " in the relationship cv.", ropy.server.ERROR_CODES["DATA_NOT_FOUND"])
        
        # logger.debug(relationships)
        # logger.debug(relationship_ids)
        
        rows = self.queries.getFeatureLocs(regionID, start, end, relationship_ids)
        
        # an to place the root level results
        featurelocs = []
        
        # a temporary hash store, keyed on uniquename, that keeps track of what features have
        # been generated so far... 
        result_map = {}
        
        logger.debug(flattened)
        
        for r in rows:
            
            root = None
            if r['l1_uniquename'] in result_map:
                root = result_map[r['l1_uniquename']]
            else:
                root = {
                    "uniquename" : r["l1_uniquename"],
                    "start" : r["l1_fmin"],
                    "end" : r["l1_fmax"],
                    "strand" : r["l1_strand"],
                    "phase" : r["l1_phase"],
                    "seqlen" : r["l1_seqlen"],
                    "relationship_type" : "",
                    "type" : r["l1_type"],
                    "is_obsolete" : r["l1_is_obsolete"],
                    "feature_id" : r["l1_feature_id"],
                    "parent" : "",
                    #"features" : []
                }
                
                if not flattened:
                    root["features"] = []
                
                result_map[r['l1_uniquename']] = root
                featurelocs.append(root)
            
            if r['l2_uniquename'] != "None": 
                # logger.debug(r['l2_uniquename'])
                if r['l2_uniquename'] in result_map:
                    l2 = result_map[r['l2_uniquename']]
                else:
                    l2 = {
                        "uniquename" : r["l2_uniquename"],
                        "start" : r["l2_fmin"],
                        "end" : r["l2_fmax"],
                        "strand" : r["l2_strand"],
                        "phase" : r["l2_phase"],
                        "seqlen" : r["l2_seqlen"],
                        "relationship_type" : r["l2_reltype"],
                        "type" : r["l2_type"],
                        "is_obsolete" : r["l2_is_obsolete"],
                        "feature_id" : r["l2_feature_id"],
                        "parent" : root["uniquename"],
                        #"features" : []
                    }
                    
                    if not flattened:
                        l2["features"] = []
                        root["features"].append(l2)
                    else:
                        featurelocs.append(l2)
                        
                    result_map[r['l2_uniquename']] = l2
            
            if r['l3_uniquename'] != "None": 
                if r['l3_uniquename'] in result_map:
                    l3 = result_map[r['l3_uniquename']]
                else:
                    l3 = {
                        "uniquename" : r["l3_uniquename"],
                        "start" : r["l3_fmin"],
                        "end" : r["l3_fmax"],
                        "strand" : r["l3_strand"],
                        "phase" : r["l3_phase"],
                        "seqlen" : r["l3_seqlen"],
                        "relationship_type" : r["l3_reltype"],
                        "type" : r["l3_type"],
                        "is_obsolete" : r["l2_is_obsolete"],
                        "feature_id" : r["l2_feature_id"],
                        "parent" : l2["uniquename"],
                        #"features" : []
                    }
                    
                    if not flattened:
                        l3["features"] = []
                        l2["features"].append(l3)
                    else:
                        featurelocs.append(l3)

                    result_map[r['l3_uniquename']] = l3
        
        result_map = None
        
        data = {
            "response" : {
                "name" : "regions/featureloc", 
                "uniqueName" : uniqueName,
                "features" : featurelocs,
            }
        }
        
        
        return data
        
    featureloc.arguments = { 
        "uniqueName" : "the uniqueName of the source feature" ,
        "start" : "the start position of the feature locations that you wish to retrieve (counting from 1)",
        "end" : "the end position of the features locations that you wish to retrieve (counting from 1)",
        "relationships" : "an optional array (i.e. it can be specified several times) detailing the relationship types you want to have, the defaults are [part_of, derives_from]",
        "flattened" : "whether you want to the results returned in a nested tree (false) or as a flattened list (true), defaults to false (nested tree)."
    }
    
    @cherrypy.expose
    @ropy.server.service_format()
    def featurelocwithnamelike(self, uniqueName, start, end, term):
        regionID = self.queries.getFeatureID(uniqueName)
        return {
            "response" : {
                "name" : "regions/featureloc", 
                "features" : self.queries.getFeatureLocsWithNameLike(regionID, start, end, term)
            }
        }
    featurelocwithnamelike.arguments = {
        "uniqueName" : "the uniqueName of the source feature" ,
        "start" : "the start position of the feature locations that you wish to retrieve (counting from 1)",
        "end" : "the end position of the features locations that you wish to retrieve (counting from 1)"
    }
        
    
    @cherrypy.expose
    @ropy.server.service_format()
    def inorganism(self, taxonID):
        """
            Returns a list of top level regions for an organism (e.g. chromosomes, contigs etc.).
        """
        organism_id = self.queries.getOrganismFromTaxon(taxonID)
        results = self.queries.getTopLevel(organism_id)
        
        data = {
           "response" : {
               "name" : "regions/inorganism",
               "taxonId" : taxonID,
               "regions" : results
           }
        }
        #data = self.api.getTopLevel(taxonID)
        return data
    
    inorganism.arguments = {
        "taxonID" : "the taxonID of the organism you want to browse"
    }
    
    
    
    
    
    # use example of how to make an alchemy controller...
    # @cherrypy.expose
    #     def test(self):
    #         from ropy.alchemy.sqlalchemy_tool import session
    #         dbs = session.query(Db)
    #         s = []
    #         for db in dbs:
    #             s.append(db.name + "\n")
    #         return s

class Organisms(BaseController):
    """
        Organism related queries.
    """
    
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def changes(self, since):
        """
            Reports all the organisms, their taxononmyIDs and a count of how many features have changed since a certain date.
        """
        logger.debug(since)
        
        organism_list = self.queries.getAllOrganismsAndTaxonIDs()
        
        organismIDs = []
        organismHash = {}
        for organism_details in organism_list:
            organism_details["count"] = 0
            organismIDs.append(organism_details["organism_id"])
            organismHash [organism_details["organism_id"]] = organism_details
        
        counts = self.queries.countAllChangedFeaturesForOrganisms(since, organismIDs)
        
        for count in counts:
            organismID = str(count[0])
            # logger.debug (organismID)
            org = organismHash[organismID]
            org["count"] = count[1]
        
        data = {
            "response" : {
                "name" : "organisms/changes",
                "since" : since,
                "results" : organismHash.values()
            }
        }
        return data
        
    changes.arguments = { "since" : "date formatted as YYYY-MM-DD" }
    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def list(self):
        """
            Lists all organisms and their taxonomyIDs. 
        """
        # logger.debug("?")
        organism_list = self.queries.getAllOrganismsAndTaxonIDs()
        # logger.debug(organism_list)
        data = {
            "response" : {
                "name" : "organisms/list",
                "organisms" : organism_list
            }
        }
        logger.debug("?")
        return data
    
    list.arguments = {}
    


class Testing(BaseController):
    """
        Test related queries.
    """

    
    
    @cherrypy.expose
    @ropy.server.service_format()
    def forceclose(self):
        """
            Forces the connection to be closed for testing.
        """
        cherrypy.thread_data.connectionFactory.getConnection().close()
        data = {
            "response" : {
                "closed" : "true"
            }
        }
        return data
    
    forceclose.arguments = {}
    
    @cherrypy.expose
    @ropy.server.service_format()
    def test(self):
        """
            Runs a query.
        """
        data = self.api.getAllOrganismsAndTaxonIDs()
        return data
    
    test.arguments = {}
    
#!/usr/bin/env python
# encoding: utf-8
"""
controllers.py

Created by Giles Velarde on 2010-02-04.
Copyright (c) 2010 Wellcome Trust Sanger Institute. All rights reserved.
"""

import sys
import os
import cherrypy

import logging

logger = logging.getLogger("charpy.controllers")

import ropy.server
import api



class FeatureController(ropy.server.RESTController):
    """
        Feature related queries.
    """
    
    def __init__(self):
        self.templateFilePath = os.path.dirname(__file__) + "/../tpl/"
    
    def init_handler(self):
        self.api = api.FeatureAPI(cherrypy.thread_data.connectionFactory)
        super(FeatureController, self).init_handler()
    
    
    @cherrypy.expose
    @ropy.server.service
    def changes(self, since, taxonomyID):
        """
            Reports all the features that have changed since a certain date.
        """
        data = self.api.changes(since, taxonomyID)
        return self.format(data, "changes")
    
    changes.arguments = { 
        "since" : "date formatted as YYYY-MM-DD", 
        "taxonomyID" : "the NCBI taxonomy ID"  
    }
    
    @cherrypy.expose
    @ropy.server.service
    def annotation_changes(self, taxonomyID, since):
        """
            Reports all the genes that have been highlighted as having annotation changes.
        """
        data = self.api.annotation_changes(taxonomyID, since)
        return self.format(data, "private_annotations")
    
    annotation_changes.arguments = { 
        "since" : "date formatted as YYYY-MM-DD", 
        "taxonomyID" : "the NCBI taxonomy ID" 
    }
    
    
    @cherrypy.expose
    @ropy.server.service
    def top(self, taxonID):
        """
            Returns a list of top level features for an organism.
        """
        data = self.api.getTopLevel(taxonID)
        return self.format(data)
    
    top.arguments = {
        "taxonID" : "the taxonID of the organism you want to browse"
    }
    
    
    
    @cherrypy.expose
    @ropy.server.service
    def featureproperties(self, **kwargs):
        
        # build the uniqueNames array from different possilble kwargs
        uniqueNames = ropy.server.get_array_from_kwargs("uniqueNames", **kwargs)
        ropy.server.get_array_from_kwargs("u", uniqueNames, **kwargs)
        
        # special case of arrays being passed using the us parameter, with the delimiter
        delimiter = kwargs["delimiter"] if "delimiter" in kwargs else ","
        if "us" in kwargs: uniqueNames.extend(kwargs["us"].split(delimiter))
        
        logger.debug(uniqueNames)
        
        if len(uniqueNames) == 0: raise ropy.server.ServerException("Please provide at least one uniqueNames / u / us parameter.", ropy.server.ERROR_CODES["MISSING_PARAMETER"])
        
        data = self.api.getFeatureProps(uniqueNames)
        return self.format(data)
    
    featureproperties.arguments = {
        "uniqueName" : "the uniqueName of the feature whose properties you're after",
        "u" : "shorthand for the uniqueName parameter",
        "us" : "a single string making up a list of uniqueNames, delimmited by the delimiter parameter",
        "delimiter" : "instructs how to split strings, defaults to a comma(,)"
    }
    

class SourceFeatureController(ropy.server.RESTController):
    """
        Source feature related queries.
    """
    
    def __init__(self):
       self.templateFilePath = os.path.dirname(__file__) + "/../tpl/"
    
    def init_handler(self):
        self.api = api.FeatureAPI(cherrypy.thread_data.connectionFactory)
        super(SourceFeatureController, self).init_handler()
    
    
    @cherrypy.expose
    @ropy.server.service
    def sequence(self, uniqueName, start, end):
        """
            Returns the sequence of a source feature.
        """
        data = self.api.getSoureFeatureSequence(uniqueName, start, end)
        return self.format(data, "source_feature_sequence")
    
    sequence.arguments = { 
        "uniqueName" : "the uniqueName of the source feature" ,
        "start" : "the start position in the sequence that you wish to retrieve (counting from 1)",
        "end" : "the end position in the sequence that you wish to retrieve (counting from 1)"
    }
    
    
    @cherrypy.expose
    @ropy.server.service
    def featureloc(self, uniqueName, start, end, **kwargs):
        """
            Returns information about all the features located on a source feature within min and max boundaries.
        """
        
        relationships = ropy.server.get_array_from_kwargs("relationships")
        if len(relationships) == 0: 
            relationships = ["part_of", "derives_from"]
        
        logger.debug(relationships)
        logger.debug(uniqueName + " : " + str(start) + " - " + str(end))
        
        data = self.api.getFeatureLoc(uniqueName, start, end, relationships)
        return self.format(data, "featureloc")
        
    featureloc.arguments = { 
        "uniqueName" : "the uniqueName of the source feature" ,
        "start" : "the start position of the feature locations that you wish to retrieve (counting from 1)",
        "end" : "the end position of the features locations that you wish to retrieve (counting from 1)",
        "relationships" : "an optional array (i.e. it can be specified several times) detailing the relationship types you want to have, the defaults are [part_of, derives_from]"
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

class OrganismController(ropy.server.RESTController):
    """
        Organism related queries.
    """
    
    def __init__(self):
        self.templateFilePath = os.path.dirname(__file__) + "/../tpl/"
    
    def init_handler(self):
        self.api = api.OrganismAPI(cherrypy.thread_data.connectionFactory)
        super(OrganismController, self).init_handler()
    
    
    @cherrypy.expose
    @ropy.server.service
    def changes(self, since):
        """
            Reports all the organisms, their taxononmyIDs and a count of how many features have changed since a certain date.
        """
        data = self.api.changes(since)
        return self.format(data, "genomes_changed")
        
    changes.arguments = { "since" : "date formatted as YYYY-MM-DD" }
    
    
    @cherrypy.expose
    @ropy.server.service
    def list(self):
        """
            Lists all organisms and their taxonomyIDs. 
        """
        data = self.api.getAllOrganismsAndTaxonIDs()
        return self.format(data)
    
    list.arguments = {}
    



class TestController(ropy.server.RESTController):
    """
        Test related queries.
    """

    def __init__(self):
        self.templateFilePath = os.path.dirname(__file__) + "/../tpl/"

    def init_handler(self):
        self.api = api.OrganismAPI(cherrypy.thread_data.connectionFactory)
        super(TestController, self).init_handler()

    
    @cherrypy.expose
    @ropy.server.service
    def forceclose(self):
        """
            Forces the connection to be closed for testing.
        """
        cherrypy.thread_data.connectionFactory.getSingleConnection().close()
        data = {
            "response" : {
                "closed" : "true"
            }
        }
        return self.format(data)
    
    forceclose.arguments = {}
    
    @cherrypy.expose
    @ropy.server.service
    def test(self):
        """
            Runs a query.
        """
        data = self.api.getAllOrganismsAndTaxonIDs()
        return self.format(data)
    
    test.arguments = {}
    
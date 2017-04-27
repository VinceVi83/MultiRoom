__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

def enum(enumName, *listValueNames):
    # Une suite d'entiers, on en crée autant
    # qu'il y a de valeurs dans l'enum.
    listValueNumbers = range(len(listValueNames))
    # création du dictionaire des attributs.
    # Remplissage initial avec les correspondances : valeur d'enum -> entier
    dictAttrib = dict(zip(listValueNames, listValueNumbers))
    # création du dictionnaire inverse. entier -> valeur d'enum
    dictReverse = dict(zip(listValueNumbers, listValueNames))
    # ajout du dictionnaire inverse dans les attributs
    dictAttrib["dictReverse"] = dictReverse
    # création et renvoyage du type
    mainType = type(enumName, (), dictAttrib)
    return mainType


ReturnCode = enum(
    "Succes",
    "Err",
    "ErrNotConnected",
    "ErrNotImplemented",
    "ErrDuplicate",
    "ErrIllegalIP",
    "ErrInvalidArgument",
    "ErrNoMusicFiles",
    "Null"
)

"""Häufige Vornamen (DE + Zuwanderungsländer + international) für die strenge Personen-Erkennung.

Zweck: Auf Team-/Kontakt-/Objektseiten und bei der Zuordnung von Telefonnummern zu Namen tauchen viele
Zwei-Wort-Zeilen auf, die formal wie Namen aussehen („Bevorzugte Kontaktart“, „Stadtbezirk Hörde“,
„Häufige Fragen“). Ein bekannter Vorname als erstes Wort ist das zuverlässigste Signal für eine Person.
Im Impressum (nach „Geschäftsführer:“) gilt die Liste NICHT – dort reicht der Kontext.
"""

from __future__ import annotations

_RAW = """
Aaron Abdul Abdullah Achim Adam Adele Adelheid Adem Adnan Adrian Adriana Agnes Ahmad Ahmed Ahmet Aileen
Aischa Alan Albert Alberto Albrecht Aleksander Aleksandra Alena Alessandro Alex Alexa Alexander Alexandra
Alexei Alexey Alexia Alexis Alf Alfons Alfred Ali Alice Alicia Alina Aline Alisa Alissa Aljoscha Alma Almut
Alois Alwin Amadeus Amal Amanda Amelie Amina Amir Amira Ana Anastasia Anatol Anders Andi Andre André Andrea
Andreas Andrej Andrew Andy Anett Anette Angela Angelika Angelina Angelo Anika Anita Anja Anke Ann Anna
Annabell Annabelle Anne Annegret Anneliese Annelie Annemarie Annett Annette Anni Annika Annkathrin Anny
Ansgar Anselm Anton Antonia Antonio Antje Anya Apostolos Ardian Ariane Arif Armin Arnd Arne Arno Arnold
Arthur Artur Arzu Asli Astrid Athanasios Attila Augustin Aurelia Axel Aycan Ayla Aylin Aynur Ayse Ayşe Aziz
Bahar Baris Barış Barbara Bärbel Bastian Bea Beate Beatrice Beatrix Behrouz Bekir Bela Ben Benedikt Benjamin
Benno Bent Berit Bernadette Bernd Bernhard Bert Berta Bertram Bettina Bianca Bianka Bilal Bill Birger Birgit
Birgitta Birte Björn Bjoern Bo Bodo Bogdan Boris Brigitte Britta Bruno Burak Burkhard Burkhardt Bülent Can
Carina Carl Carla Carlo Carlos Carmen Carola Carolin Carolina Caroline Carsten Catharina Catherine Cathrin
Cecilia Cedric Celina Celine Cem Cengiz Chantal Charlotte Chiara Chris Christa Christel Christian Christiane
Christin Christina Christine Christoph Christopher Cindy Claas Claudia Claudio Claus Clemens Colin Conny
Constantin Constanze Cora Cordula Corinna Corinne Cornelia Cornelius Cosima Cristina Dagmar Damian Dana
Daniel Daniela Daniele Danijel Danny Dario Darius Dave David Davide Dawid Dean Deborah Denis Deniz Dennis
Derya Desiree Detlef Detlev Diana Diane Diego Dierk Dieter Dietmar Dietrich Dilara Dimitri Dimitrios Dina
Dirk Dogan Doğan Dominic Dominik Dominika Dominique Domenico Donald Dora Doreen Doris Dorit Dorothea
Dorothee Dursun Ebru Eckard Eckart Eckhard Eckhardt Edda Edgar Edith Eduard Edward Edwin Egon Ehsan Eike
Elena Eleni Eleonore Elfriede Elias Elif Elisa Elisabeth Elise Elke Ella Ellen Elli Elmar Elvira Emanuel
Emil Emilia Emilie Emily Emine Emma Emmanuel Emre Enes Engin Enrico Enrique Enzo Erdal Erdogan Erhan Erhard
Eric Erich Erik Erika Erkan Ernst Erol Erwin Esra Esther Eugen Eva Evelin Eveline Evelyn Ewald Fabian
Fabienne Fabio Fadime Falk Falko Farah Farid Fatih Fatima Fatma Federico Felicitas Felix Ferdinand Ferhat
Fikret Filip Filippo Finn Fiona Florian Folke Frances Francesca Francesco Francisco Frank Franka Franz
Franziska Frauke Fred Freddy Frederic Frederik Frederike Fredi Friedemann Friederike Friedhelm Friedrich
Frieder Fritz Fynn Gabi Gabriel Gabriela Gabriele Gabriella Gaby Gareth Gebhard Georg George Georgia
Georgios Gerald Geraldine Gerd Gerda Gerhard Gerhardt Gerlinde Gernot Gero Gerold Gerrit Gert Gertrud Gesa
Gesine Giacomo Gianluca Gianni Gina Giovanni Gisbert Gisela Giulia Giuseppe Gökhan Gordon Goran Gottfried
Götz Grace Gregor Greta Grit Gudrun Guido Gunda Gunnar Günter Günther Gunter Gunther Gustav Hakan Halil
Hamza Hanna Hannah Hannelore Hannes Hanno Hans Hansjörg Hardy Harald Harold Harry Hartmut Hasan Hassan
Hatice Hauke Hayrettin Hedwig Heide Heidemarie Heidi Heidrun Heike Heiko Heiner Heinrich Heinz Helen Helena
Helene Helga Helge Helma Helmut Helmuth Hendrik Henning Henri Henrik Henriette Henry Herbert Heribert
Hermann Herta Hertha Hilde Hildegard Hilke Hinrich Holger Horst Hubert Hubertus Hugo Hülya Hussein Ibrahim
İbrahim Ida Ignaz Igor Ilhan İlhan Ilka Ilona Ilse Imke Ina Ines Inga Ingborg Inge Ingeborg Ingo Ingolf
Ingrid Ioannis Irene Irina Iris Irma Irmgard Isa Isabel Isabell Isabella Isabelle Ismail Isolde Ivan Ivana
Ivo Jacek Jack Jacqueline Jakob Jakub James Jan Jana Janet Janette Janick Janina Janine Janis Janna Jannik
Jannis Janosch Jaroslaw Jasmin Jasmina Jason Jean Jeanette Jeannette Jeffrey Jenna Jennifer Jenny Jens
Jeremias Jérôme Jerome Jessica Jessika Jil Jill Jo Joachim Joana Joanna Jochen Joe Joel Johann Johanna
Johannes John Jonas Jonathan Jörg Joerg Jörn Joern Jose José Josef Josefine Joseph Josephine Joshua Jost
Juan Judith Jule Julia Julian Juliane Julie Julien Juliette Julius Jürgen Juergen Justin Justus Jutta Kai
Kaja Kalle Kamil Karen Karim Karin Karina Karl Karla Karlheinz Karola Karolin Karolina Karoline Karsten
Kasimir Kaspar Katarina Katarzyna Katharina Käthe Kathi Kathleen Kathrin Kathy Kati Katja Katrin Kay Kemal
Kenan Kenneth Kerem Kerstin Kevin Kilian Kim Kira Kirsten Kirstin Klara Klaus Knut Konrad Konstantin
Konstantinos Kolja Kornelia Kristian Kristin Kristina Kristine Krystian Krzysztof Kurt Lambert Lara Larissa
Lars Laura Laurenz Lea Leah Leander Lena Lennard Lennart Lenny Leo Leon Leonard Leonardo Leonhard Leonie
Leopold Leszek Levent Levi Lia Liane Lidia Lieselotte Lilia Lilian Lilli Lilly Lina Linda Linus Lisa Lisbeth
Liselotte Lissy Livia Lore Loredana Lorenz Loretta Lothar Louis Louisa Louise Luca Lucas Lucia Lucie Lucy
Ludger Ludwig Luigi Luis Luisa Luise Lukas Lutz Lydia Lynn Maciej Madeleine Magdalena Magnus Mahmoud Mahmut
Maik Maike Maja Malte Mandy Manfred Manuel Manuela Mara Marc Marcel Marcell Marcella Marcin Marco Marcus
Marek Maren Margareta Margarete Margaretha Margarethe Margit Margot Margrit Maria Mariam Marian Mariana
Marianne Marie Marielle Marietta Marika Marina Mario Marion Marius Mariusz Marko Markus Marla Marlen Marlene
Marlies Marlis Marta Martha Martin Martina Marvin Mary Maryam Mateusz Mathias Mathilde Matteo Matthew
Matthias Maurice Maurizio Max Maxi Maxim Maximilian Maya Mehmet Melanie Melek Melina Melissa Melvin Meral
Merle Mert Merve Meryem Mesut Mia Michael Michaela Michel Michele Michelle Miguel Mihaela Mike Mila Milan
Milena Milica Mina Mira Miriam Mirja Mirjam Mirko Miroslav Mohamed Mohammad Mohammed Mona Monika Monique
Moritz Murat Mustafa Nabil Nadin Nadine Nadja Nancy Naomi Natalia Natalie Natascha Nathalie Nazan Neele Nele
Nevin Niclas Nico Nicola Nicolas Nicolaus Nicole Niels Nihat Nikita Niklas Niko Nikola Nikolai Nikolaj
Nikolaos Nikolas Nikolaus Nils Nina Nino Noah Nora Norbert Norman Nour Nuray Nurhan Nuri Ocean Ökkes Okan
Olaf Ole Oleg Olga Oliver Olivia Omar Omer Ömer Onur Orhan Orkan Osman Oskar Oswald Otto Ottmar Özge Özgür
Özlem Pablo Paolo Pascal Patricia Patrick Patrizia Paul Paula Paulina Pauline Pavel Pawel Peer Peggy Pelin
Pero Pete Peter Petra Philip Philipp Philippe Pia Piet Pierre Piotr Pit Quirin Rabea Rafael Rafal Raffaele
Rahel Raik Raimund Rainer Ralf Ralph Ramin Ramona Randolf Raphael Raphaela Raul Ray Rebecca Rebekka Regina
Regine Reiner Reinhard Reinhardt Reinhild Reinhold Remo Renate Renato Rene René Reza Ricarda Riccardo
Richard Rico Rita Robert Roberta Roberto Robin Rocco Roderich Rodrigo Roger Roland Rolf Roman Romy Ron
Ronald Ronja Ronny Rosa Rosalie Rosemarie Rosi Roswitha Rouven Ruben Rudi Rudolf Rüdiger Ruediger Ruth
Sabine Sabrina Sacha Sahin Şahin Said Salih Salvatore Sam Samantha Samir Samuel Sandra Sandro Sandy Sanja
Sara Sarah Sascha Saskia Sean Sebastian Sedat Selim Selin Selina Selma Semih Semra Serdar Serena Sergej
Sergio Serkan Sevda Sevim Severin Sevgi Sibel Sibylle Siegbert Siegfried Sieglinde Siegmar Siegmund Sigrid
Sigrun Silas Silja Silke Silvana Silvia Silvio Simon Simona Simone Sina Sinan Sissi Slavko Sofia Sofie Sonja
Sophia Sophie Sören Soeren Stavros Stefan Stefanie Steffen Steffi Stella Stephan Stephanie Stephen Steve
Steven Stine Sükrü Şükrü Suleyman Süleyman Susan Susann Susanna Susanne Susi Suzanne Sven Svenja Swantje
Sybille Sylke Sylvia Sylvio Tabea Tamara Tanja Tarek Tarik Tatjana Tayfun Ted Teresa Thea Theo Theodor
Theodora Theresa Therese Thies Thilo Thomas Thoralf Thorben Thorsten Tiago Til Till Tilman Tilo Tim Timm
Timo Timon Timothy Tina Tino Tiziana Tobias Tom Tomas Tomasz Toni Tony Torben Torsten Traudel Traute Trude
Tugba Tuğba Tülay Uda Udo Ufuk Ulf Uli Ulla Ulrich Ulrike Umut Ursel Ursula Uta Ute Uwe Valentin Valentina
Valentino Valeria Valerie Vanessa Vasilios Vera Verena Veronika Veronica Vicky Victor Victoria Viktor
Viktoria Vincent Vincenzo Viola Violetta Vito Vivian Viviane Vladimir Volkan Volker Volkmar Waldemar Walter
Walther Waltraud Werner Wiebke Wilfried Wilhelm Wilhelmine Willi William Willy Wim Winfried Wolf Wolfgang
Wolfram Xenia Yannick Yannik Yasemin Yasin Yasmin Yavuz Yilmaz Yılmaz Yunus Yusuf Yvonne Zafer Zehra Zeynep
Zoe Zoran Zübeyde
"""

VORNAMEN: frozenset[str] = frozenset(w.casefold() for w in _RAW.split())


def is_known_first_name(token: str) -> bool:
    """„Hans-Peter“, „Anna-Lena“ → mindestens ein Teil muss bekannt sein; Anrede/Titel sind hier schon weg."""
    if not token:
        return False
    parts = [p for p in token.replace("‐", "-").split("-") if p]
    return any(p.casefold() in VORNAMEN for p in parts)

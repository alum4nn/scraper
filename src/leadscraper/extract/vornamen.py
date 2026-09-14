"""Häufige Vornamen (DE + Zuwanderungsländer + international) für die strenge Personen-Erkennung.

Zweck: Auf Team-/Kontakt-/Objektseiten und bei der Zuordnung von Telefonnummern zu Namen tauchen viele
Zwei-Wort-Zeilen auf, die formal wie Namen aussehen („Bevorzugte Kontaktart“, „Stadtbezirk Hörde“,
„Häufige Fragen“). Ein bekannter Vorname als erstes Wort ist das zuverlässigste Signal für eine Person.
Im Impressum (nach „Geschäftsführer:“) gilt die Liste NICHT – dort reicht der Kontext.
"""

from __future__ import annotations

_RAW = """
Aaliyah Aaron Abdul Abdullah Abel Achim Adam Adele Adelheid Adem Adnan Adrian Adriana Agnes Ahmad Ahmed
Ahmet Aileen Aischa Alan Albert Alberto Albrecht Aleksander Aleksandra Alena Alessandro Alessia Alex Alexa
Alexander Alexandra Alexei Alexey Alexia Alexis Alf Alfons Alfred Ali Alice Alicia Alina Aline Alisa Alissa
Aljoscha Alma Almut Alois Alwin Amadeus Amal Amalia Amanda Amelie Amin Amina Amir Amira Ana Anastasia Anatol
Anders Andi Andre Andrea Andreas Andrej Andrew Andrin André Andy Anett Anette Angela Angelika Angelina
Angelo Anika Anita Anja Anke Ann Anna Annabell Annabelle Anne Annegret Annelie Anneliese Annemarie Annett
Annette Anni Annika Annkathrin Anny Anouk Anselm Ansgar Antje Anton Antonia Antonio Anya Apostolos Arda
Ardian Arian Ariane Arif Armin Arnd Arne Arno Arnold Artem Arthur Artur Arzu Asli Astrid Athanasios Attila
Augustin Aurel Aurelia Ava Axel Aycan Ayla Aylin Aynur Ayse Ayşe Aziz Bahar Baran Barbara Baris Barış
Bastian Bea Beate Beatrice Beatrix Behrouz Bekir Bela Ben Benedikt Benjamin Bennet Benno Bent Berit
Bernadette Bernd Bernhard Bert Berta Bertram Bettina Bianca Bianka Bilal Bill Birger Birgit Birgitta Birte
Bjarne Bjoern Björn Bo Bodo Bogdan Boris Brigitte Britta Bruno Burak Burkhard Burkhardt Bärbel Bülent Can
Carina Carl Carla Carlo Carlos Carlotta Carmen Carola Carolin Carolina Caroline Carsten Caspar Catharina
Catherine Cathrin Cecilia Cedric Celina Celine Cem Cengiz Chantal Charlotte Chiara Chris Christa Christel
Christian Christiane Christin Christina Christine Christoph Christopher Cindy Claas Clara Claudia Claudio
Claus Clemens Colin Connor Conny Constantin Constanze Cora Cordula Corinna Corinne Cornelia Cornelius Cosima
Cristina Curt Dagmar Damian Dana Daniel Daniela Daniele Daniil Danijel Danilo Danny Dario Darius Dave David
Davide Dawid Dean Deborah Denis Deniz Dennis Derya Desiree Detlef Detlev Devin Diana Diane Diego Dierk
Dieter Dietmar Dietrich Dilara Dimitri Dimitrios Dina Dion Dirk Dogan Domenico Dominic Dominik Dominika
Dominique Donald Dora Doreen Doris Dorit Dorothea Dorothee Doğan Dursun Dustin Ebru Eckard Eckart Eckhard
Eckhardt Edda Eddy Edgar Edith Eduard Edward Edwin Egon Ehsan Eike Elena Eleni Eleonore Elfriede Elia Elian
Elias Elif Elisa Elisabeth Elise Elke Ella Ellen Elli Elmar Elvira Emanuel Emely Emil Emilia Emilian Emilie
Emily Emine Emir Emma Emmanuel Emmi Emre Enes Engin Enie Enno Enrico Enrique Enzo Erdal Erdogan Eren Erhan
Erhard Eric Erich Erik Erika Erkan Ernst Erol Erwin Esra Estelle Esther Ethan Eugen Eva Evelin Eveline
Evelyn Ewald Fabian Fabien Fabienne Fabio Fadime Falk Falko Farah Farid Fatih Fatima Fatma Federico Felicia
Felicitas Felix Ferdinand Ferhat Fiete Fikret Filip Filippo Finja Finn Fiona Florian Folke Frances Francesca
Francesco Francisco Frank Franka Franz Franziska Frauke Fred Freddy Frederic Frederik Frederike Fredi Frida
Frieda Friedemann Frieder Friederike Friedhelm Friedrich Fritz Fynn Gabi Gabriel Gabriela Gabriele Gabriella
Gaby Gareth Gebhard Georg George Georgia Georgios Gerald Geraldine Gerd Gerda Gerhard Gerhardt Gerlinde
Gernot Gero Gerold Gerrit Gert Gertrud Gesa Gesine Giacomo Gian Gianluca Gianni Gideon Gina Giovanni Gisbert
Gisela Giulia Giuseppe Goran Gordon Gottfried Grace Gregor Greta Grit Gudrun Guido Gunda Gunnar Gunter
Gunther Gustav Gökhan Götz Günter Günther Hailey Hakan Halil Hamza Hanna Hannah Hannelore Hannes Hanno Hans
Hansjörg Harald Hardy Harold Harry Hartmut Hasan Hassan Hatice Hauke Hayrettin Hedwig Heide Heidemarie Heidi
Heidrun Heike Heiko Heiner Heinrich Heinz Helen Helena Helene Helga Helge Helma Helmut Helmuth Hendrik
Henning Henri Henriette Henrik Henry Herbert Heribert Hermann Herta Hertha Hilde Hildegard Hilke Hinrich
Holger Horst Hubert Hubertus Hugo Hussein Hülya Ibrahim Ida Ignaz Igor Ilhan Ilias Ilja Ilka Ilona Ilse Ilva
Imke Imran Ina Ines Inga Ingborg Inge Ingeborg Ingo Ingolf Ingrid Ioannis Irene Irina Iris Irma Irmgard Isa
Isabel Isabell Isabella Isabelle Ismail Isolde Ivan Ivana Ivo İbrahim İlhan Jacek Jack Jacqueline Jakob
Jakub James Jamie Jan Jana Janet Janette Janick Janina Janine Janis Janna Janne Jannek Jannes Jannik Jannis
Janosch Jara Jaron Jaroslaw Jasmin Jasmina Jason Jasper Jayden Jean Jeanette Jeannette Jeffrey Jella Jenna
Jennifer Jenny Jens Jeremias Jerome Jesse Jessica Jessika Jessy Jette Jil Jill Jim Jo Joachim Joana Joanna
Jochen Joe Joel Joerg Joern Johann Johanna Johannes John Jolie Jon Jonah Jonas Jonathan Jonte Jordan Jorin
Joris Jose Josef Josefa Josefine Joseph Josephine Joshua Jost Josua José Juan Judith Juergen Jule Julia
Julian Juliane Julie Julien Juliette Julius Juna Juri Justin Justus Jutta Jérôme Jörg Jörn Jürgen Kai Kaja
Kalle Kamil Karen Karim Karin Karina Karl Karla Karlheinz Karola Karolin Karolina Karoline Karsten Kasimir
Kaspar Katarina Katarzyna Katharina Kathi Kathleen Kathrin Kathy Kati Katja Katrin Kay Kaya Keira Kemal
Kenan Kenneth Kerem Kerstin Kevin Kian Kiana Kiara Kilian Kim Kimi Kira Kirill Kirsten Kirstin Klara Klaus
Knut Kolja Konrad Konstantin Konstantinos Korbinian Kornelia Kristian Kristin Kristina Kristine Krystian
Krzysztof Kurt Käthe Lambert Lana Lara Larissa Lars Lasse Laura Laurens Laurenz Lea Leah Lean Leander
Leandro Lena Leni Lennard Lennart Lenny Leo Leon Leonard Leonardo Leonhard Leonie Leopold Leroy Leszek
Levent Levi Levin Levke Lia Liam Lian Liana Liane Lidia Lieselotte Lilia Lilian Lilli Lilly Lina Linda Lino
Linus Lio Lion Lisa Lisbeth Liselotte Lissy Livia Lore Loredana Lorenz Loretta Lothar Lotta Lotte Louis
Louisa Louise Luan Luca Lucas Lucia Lucie Lucy Ludger Ludwig Luigi Luis Luisa Luise Luk Luka Lukas Luke Luna
Lupo Lutz Lydia Lynn Maciej Madeleine Madita Magdalena Magnus Mahmoud Mahmut Maik Maike Maja Maksim Malia
Malik Malin Malte Mandy Manfred Manuel Manuela Mara Marc Marcel Marcell Marcella Marcin Marco Marcus Mareike
Marek Maren Margareta Margarete Margaretha Margarethe Margit Margot Margrit Maria Mariam Marian Mariana
Marianne Marie Marielle Marietta Marika Marina Mario Marion Marit Marius Mariusz Mark Marko Markus Marla
Marlen Marlene Marlies Marlis Marlon Marta Martha Martin Martina Marvin Mary Maryam Mateo Mateusz Mathias
Mathilda Mathilde Mathis Mats Matteo Matthew Matthias Matti Maurice Maurizio Max Maxi Maxim Maximilian Maya
Mehmet Meike Melanie Melek Melia Melina Melissa Melvin Meral Merle Merlin Mert Merve Meryem Mesut Mia
Michael Michaela Michel Michele Michelle Mick Mieke Miguel Mihaela Mika Mike Mila Milan Milena Milica Milo
Mina Mio Mira Miran Mirco Miriam Mirja Mirjam Mirko Miroslav Mohamed Mohammad Mohammed Mona Monika Monique
Moritz Muhammed Murat Musa Mustafa Nabil Nadin Nadine Nadja Nala Nancy Naomi Natalia Natalie Natascha
Nathalie Nathan Nazan Neele Nele Neo Nepomuk Nevin Nevio Nick Niclas Nico Nicola Nicolas Nicolaus Nicole
Niels Nihat Nika Nike Nikita Niklas Niko Nikola Nikolai Nikolaj Nikolaos Nikolas Nikolaus Nils Nina Nino
Noah Noel Nora Norbert Norman Nour Nuray Nurhan Nuri Ocean Odin Okan Oke Olaf Ole Oleg Olga Oliver Olivia
Omar Omer Onur Orhan Orkan Oscar Oskar Osman Oswald Ottmar Otto Pablo Paolo Pascal Patricia Patrick Patrizia
Paul Paula Paulina Pauline Pavel Pawel Peer Peggy Pelin Penelope Pepe Pero Pete Peter Petra Phil Philip
Philipp Philippa Philippe Phoebe Pia Pierre Piet Piotr Pit Pius Quentin Quirin Rabea Rafael Rafal Raffaele
Rahel Raik Raimund Rainer Ralf Ralph Ramin Ramon Ramona Randolf Raphael Raphaela Rasmus Raul Ray Rebecca
Rebekka Regina Regine Reiner Reinhard Reinhardt Reinhild Reinhold Remo Renate Renato Rene René Reza Ricarda
Ricardo Riccardo Richard Rico Rieke Rita Robby Robert Roberta Roberto Robin Rocco Roderich Rodrigo Roger
Roland Rolf Roman Romina Romy Ron Ronald Ronja Ronny Rosa Rosalie Rosemarie Rosi Roswitha Rouven Ruben Ruby
Rudi Rudolf Ruediger Ruth Ryan Rüdiger Sabine Sabrina Sacha Sahin Said Salih Salvatore Sam Samantha Samir
Sammy Samuel Sandra Sandro Sandy Sanja Santino Sara Sarah Sascha Saskia Sean Sebastian Sedat Selim Selin
Selina Selma Semih Semra Sena Serdar Serena Sergej Sergio Serkan Sevda Severin Sevgi Sevim Shawn Sibel
Sibylle Sidney Siegbert Siegfried Sieglinde Siegmar Siegmund Sigrid Sigrun Silas Silja Silke Silvana Silvia
Silvio Simeon Simon Simona Simone Sina Sinan Sissi Slavko Smilla Soeren Sofia Sofie Sole Soner Sonja Sophia
Sophie Stavros Stefan Stefanie Steffen Steffi Stella Stephan Stephanie Stephen Steve Steven Stine Suleyman
Sunny Susan Susann Susanna Susanne Susi Suzanne Svea Sven Svenja Swantje Sybille Sylke Sylvia Sylvio Sören
Sükrü Süleyman Tabea Taha Tamara Tamina Tamino Tanja Tara Tarek Tarik Tatjana Tayfun Tayler Taylor Ted Teo
Teresa Tessa Thalia Thea Theo Theodor Theodora Theresa Therese Thies Thilo Thomas Thoralf Thorben Thorsten
Tiago Til Tilda Till Tilman Tilo Tim Timm Timo Timon Timothy Tina Tino Tizian Tiziana Tobias Tom Tomas
Tomasz Tomke Tommy Toni Tony Torben Tore Torsten Traudel Traute Tristan Trude Tugba Tuğba Tyler Tülay Uda
Udo Ufuk Ulf Uli Ulla Ulrich Ulrike Umut Urs Ursel Ursula Uta Ute Uwe Valentin Valentina Valentino Valeria
Valerie Vanessa Vasilios Veit Vera Verena Veronica Veronika Vicky Victor Victoria Viktor Viktoria Vincent
Vincenzo Viola Violetta Vito Vitus Vivian Viviane Vladimir Volkan Volker Volkmar Waldemar Walter Walther
Waltraud Werner Wibke Wiebke Wilfried Wilhelm Wilhelmine Willi William Willy Wim Winfried Wolf Wolfgang
Wolfram Xaver Xenia Yannick Yannik Yannis Yara Yasemin Yasin Yasmin Yavuz Yilmaz Younes Yuna Yunus Yusuf
Yvonne Yılmaz Zafer Zehra Zeno Zeynep Zoe Zora Zoran Zübeyde Ökkes Ömer Özge Özgür Özlem Şahin Şükrü
"""

VORNAMEN: frozenset[str] = frozenset(w.casefold() for w in _RAW.split())


def is_known_first_name(token: str) -> bool:
    """„Hans-Peter“, „Anna-Lena“ → mindestens ein Teil muss bekannt sein; Anrede/Titel sind hier schon weg."""
    if not token:
        return False
    parts = [p for p in token.replace("‐", "-").split("-") if p]
    return any(p.casefold() in VORNAMEN for p in parts)

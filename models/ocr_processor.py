import base64
from pdf2image import convert_from_path, convert_from_bytes
import google.generativeai as genai
from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import cachetools
import json 
import os
import tempfile
import fitz
from PIL import Image
import io



# Set the path to the Poppler bin directory
poppler_path = r"C:\Users\NajibNOUISSER\Release-24.08.0-0\poppler-24.08.0\Library\bin"  # Replace with your Poppler path

class OCRProcessor(models.Model):
    _name = 'purchase.order.ocr.wizard'
    _description = 'OCR Processor for Invoice Extraction'

    # Champs du modèle
    invoice_file = fields.Binary(string="Invoice File", required=True)
    vendor_name = fields.Char(string="Vendor Name")


    def process_document(self):
        """
        Process the invoice file using OCR and create a Purchase Order.
        """
        for wizard in self:
            # if not wizard.invoice_file:
            #     raise UserError("Veuillez fournir un fichier de facture à traiter.")

            try:
                # Étape 1 : Décoder le fichier PDF
                invoice_data = base64.b64decode(self.invoice_file)

                # Étape 2 : Sauvegarder le fichier PDF temporairement
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                    temp_pdf.write(invoice_data)
                    temp_pdf_path = temp_pdf.name  # Chemin temporaire du fichier PDF

                # Étape 3 : Convertir le PDF en images avec la fonction pdf_to_images
                images = self.pdf_to_images(temp_pdf_path)

                # Vérification : Assurez-vous que des images ont été extraites
                if not images:
                    raise UserError("Impossible de convertir le fichier PDF en images.")

                # Étape 4 : Sauvegarder temporairement les images et traiter
                extracted_text = ""
                for image in images:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_image:
                        # Sauvegarde temporaire de l'image pour OCR
                        image.save(temp_image.name, format="JPEG")
                        # Extraire le texte de l'image temporaire via OCR
                        extracted_text += self.extract_text_from_image(temp_image.name) + "\n"

                # Étape 5 : Nettoyage du texte extrait
                clean_version = self.clean_text(extracted_text)

                # Étape 6 : Analyse du texte pour en extraire des données structurées
                extracted_data = self.parse_quotation_text(clean_version)

                # Validation des données essentielles
                if not extracted_data.get('salesperson') or not extracted_data.get('order_line'):
                    raise UserError("Les données extraites de la facture sont incomplètes ou invalides.")

                # Étape 7 : Création de la commande d'achat
                purchase_order = self.env['purchase.order'].create({
                    'partner_id': extracted_data['salesperson'],  # ID du fournisseur
                    'order_line': extracted_data['order_line'],  # Lignes de commande
                    'date_order': extracted_data['quotation_date'],  # Date de commande
                    'name': extracted_data['name'],  # Nom/description de la commande
                })

                # Lier la commande d'achat au wizard
                wizard.purchase_order_id = purchase_order.id

                # Étape 8 : Retour d'une action pour ouvrir la commande créée
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'view_mode': 'form',
                    'res_id': wizard.purchase_order.id,
                    'target': 'current',
                }

            except Exception as e:
                # Gestion des erreurs et affichage d'un message clair
                raise UserError(f"Erreur lors du traitement de la facture : {str(e)}")

    def extract_text_from_image(self, image_path):
        """
        Extrait le texte d'une image en utilisant l'API Gemini.

        Args:
            image_path (str): Chemin de l'image locale à traiter.

        Returns:
            str: Texte extrait de l'image.
        """
        # Configurez l'API Gemini
        genai.configure(api_key="AIzaSyDaP8ZOx1C65sCTHuT-7cexhwfl2xf71lQ")

        # Chargez le modèle Gemini
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Lisez l'image locale et encodez-la en base64
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Préparez le prompt pour l'extraction de texte
        prompt = "Extract the text from the image"

        # Envoyez l'image et le prompt au modèle Gemini
        response = model.generate_content(
            [
                {"mime_type": "image/jpeg", "data": image_data},  # Image encodée en base64
                prompt,  # Prompt pour extraire le texte
            ]
        )

        # Retournez le texte extrait
        return response.text


    def parse_quotation_text(text):
        """
        Parse le texte extrait pour en extraire les informations structurées.

        Args:
            text (str): Texte extrait de l'image ou du PDF.

        Returns:
            dict: Un dictionnaire contenant les informations structurées.
        """
        # Initialiser la structure de données
        quotation_data = {
            "quotation_number": None,
            "date_order": None,
            "expiration_date": None,
            "salesperson": None,
            "products": [],
            "total_amount": None,
        }

        # Diviser le texte en lignes
        lines = text.splitlines()

        # Variables temporaires pour stocker les données
        current_section = None

        # Parcourir chaque ligne pour extraire les données
        for line in lines:
            line = line.strip()  # Supprimer les espaces inutiles

            # Ignorer les lignes vides
            if not line:
                continue

            # Détecter les sections
            if "Quotation #" in line:
                quotation_data["quotation_number"] = line.split("Quotation #")[-1].strip()
            elif "Quotation Date:" in line:
                current_section = "quotation_date"
            elif "Expiration:" in line:
                current_section = "expiration_date"
            elif "Salesperson:" in line:
                current_section = "salesperson"
            elif "Description" in line:
                current_section = "description"
            elif "Quantity" in line:
                current_section = "quantity"
            elif "Unit Price" in line:
                current_section = "unit_price"
            elif "Taxes" in line:
                current_section = "taxes"
            elif "Amount" in line:
                current_section = "amount"
            elif "Total" in line:
                current_section = "total_amount"
            elif "Page:" in line:
                current_section = None  # Fin de la section pertinente

            # Extraire les données en fonction de la section actuelle
            if current_section == "quotation_date":
                quotation_data["quotation_date"] = line.strip()
            elif current_section == "expiration_date":
                quotation_data["expiration_date"] = line.strip()
            elif current_section == "salesperson":
                quotation_data["salesperson"] = line.strip()
            elif current_section == "description":
                # Ignorer la ligne "Description" elle-même
                if line.lower() != "description":
                    product = {"description": line.strip()}
                    quotation_data["products"].append(product)
            elif current_section == "quantity":
                if quotation_data["products"]:
                    quotation_data["products"][-1]["quantity"] = line.strip()
            elif current_section == "unit_price":
                if quotation_data["products"]:
                    quotation_data["products"][-1]["unit_price"] = line.strip()
            elif current_section == "taxes":
                if quotation_data["products"]:
                    quotation_data["products"][-1]["taxes"] = line.strip()
            elif current_section == "amount":
                if quotation_data["products"]:
                    quotation_data["products"][-1]["amount"] = line.strip()
            elif current_section == "total_amount":
                quotation_data["total_amount"] = line.strip()

        return quotation_data


    def clean_text(text):
        """
        Nettoie le texte en supprimant les caractères indésirables comme | et *.

        Args:
            text (str): Texte à nettoyer.

        Returns:
            str: Texte nettoyé.
        """
        # Supprimer les caractères indésirables
        text = text.replace("|", "").replace("*", "")
        return text



    # def pdf_to_images(pdf_path, output_folder=None, fmt="png", dpi=300):
    #     """
    #     Convertit un fichier PDF en une liste d'images.

    #     Args:
    #         pdf_path (str): Chemin du fichier PDF.
    #         output_folder (str, optional): Dossier de sortie pour enregistrer les images. Si None, les images ne sont pas enregistrées.
    #         fmt (str, optional): Format de l'image (par défaut : "png").
    #         dpi (int, optional): Résolution des images (par défaut : 300).

    #     Returns:
    #         list: Liste des images (objets PIL.Image).
    #     """
    #     # Convertir le PDF en images
    #     images = convert_from_path(pdf_path, dpi=dpi, fmt=fmt)

    #     # Enregistrer les images dans le dossier de sortie si spécifié
    #     if output_folder:
    #         import os
    #         if not os.path.exists(output_folder):
    #             os.makedirs(output_folder)
    #         for i, image in enumerate(images):
    #             image.save(os.path.join(output_folder, f"page_{i + 1}.{fmt}"), fmt.upper())

    #     return images
    

    def pdf_to_images(pdf_path, output_folder=None, fmt="png", dpi=300):
        """
        Convertit un fichier PDF en une liste d'images.

        Args:
            pdf_path (str): Chemin du fichier PDF.
            output_folder (str, optional): Dossier de sortie pour enregistrer les images. Si None, les images ne sont pas enregistrées.
            fmt (str, optional): Format de l'image (par défaut : "png").
            dpi (int, optional): Résolution des images (par défaut : 300).

        Returns:
            list: Liste des images (objets PIL.Image).
        """
        # Ouvrir le document PDF
        doc = fitz.open(pdf_path)

        # Liste pour stocker les images PIL
        images = []

        # Convertir chaque page du PDF en image
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            
            # Obtenir un pixmap avec la résolution désirée
            pix = page.get_pixmap(dpi=dpi)
            
            # Convertir le pixmap en image PIL
            image = Image.open(io.BytesIO(pix.tobytes("png")))  # Conversion en image PIL
            images.append(image)
            
            # Enregistrer l'image si un dossier de sortie est spécifié
            if output_folder:
                if not os.path.exists(output_folder):
                    os.makedirs(output_folder)
                img_path = os.path.join(output_folder, f"page_{page_num + 1}.{fmt}")
                image.save(img_path, fmt.upper())  # Sauvegarde dans le format désiré

        # Fermer le document pour libérer les ressources
        doc.close()

        return images

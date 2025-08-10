<template>
    <n-button 
      type="info" 
      :disabled="selectedPassengerIds.length === 0" 
      @click="exportToPdf"
    >
      Export Passenger Details
    </n-button>
</template>

<script setup lang="ts">
import { useMessage, NButton } from 'naive-ui';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

// Define the shape of the passenger object for better type safety
interface Passenger {
  id: number;
  name: string;
  contact?: string;
  passport_number?: string;
  salutation?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  zip_code?: string;
  fathers_name?: string;
  mothers_name?: string;
  date_of_birth?: string;
  passport_issue_date?: string;
  passport_expiry?: string;
  nationality?: string;
  active?: boolean;
}

const props = defineProps({
  passengers: {
    type: Array as () => Passenger[],
    required: true,
  },
  selectedPassengerIds: {
    type: Array as () => number[],
    default: () => [],
  },
});

const message = useMessage();

const exportToPdf = () => {
  if (props.selectedPassengerIds.length === 0) {
    message.warning('Please select at least one passenger to export.');
    return;
  }

  const selectedPassengers = props.passengers.filter(p => props.selectedPassengerIds.includes(p.id));

  const doc = new jsPDF();
  const today = new Date().toLocaleDateString();
  let yOffset = 20;

  // Function to add a page and header if needed
  const checkPageBreak = (height: number) => {
    if (yOffset + height > 280) { // Approx. page height
      doc.addPage();
      yOffset = 20;
    }
  };

  selectedPassengers.forEach((passenger, index) => {
    checkPageBreak(120); // Estimated space for one passenger's details

    // Header for each passenger profile
    doc.setFontSize(16);
    doc.text(`Passenger Profile: ${passenger.name}`, 14, yOffset);
    doc.setFontSize(10);
    yOffset += 8;
    doc.line(14, yOffset, 196, yOffset); // Separator line
    yOffset += 8;

    // Contact and Personal Details
    doc.setFontSize(12);
    doc.text('Personal Details', 14, yOffset);
    doc.setFontSize(10);
    yOffset += 6;
    doc.text(`Name: ${passenger.salutation || ''} ${passenger.name || ''}`, 14, yOffset);
    yOffset += 6;
    doc.text(`Date of Birth: ${passenger.date_of_birth ? new Date(passenger.date_of_birth).toLocaleDateString() : 'N/A'}`, 14, yOffset);
    doc.text(`Contact: ${passenger.contact || 'N/A'}`, 100, yOffset);
    yOffset += 6;
    doc.text(`Father's Name: ${passenger.fathers_name || 'N/A'}`, 14, yOffset);
    doc.text(`Mother's Name: ${passenger.mothers_name || 'N/A'}`, 100, yOffset);
    yOffset += 10;

    // Passport Details
    doc.setFontSize(12);
    doc.text('Passport & Nationality', 14, yOffset);
    doc.setFontSize(10);
    yOffset += 6;
    doc.text(`Passport Number: ${passenger.passport_number || ''}`, 14, yOffset);
    doc.text(`Passport Issue Date: ${passenger.passport_issue_date ? new Date(passenger.passport_issue_date).toLocaleDateString() : 'N/A'}`, 100, yOffset);
    yOffset += 6;
    doc.text(`Passport Expiry: ${passenger.passport_expiry ? new Date(passenger.passport_expiry).toLocaleDateString() : 'N/A'}`, 14, yOffset);
    doc.text(`Nationality: ${passenger.nationality || 'N/A'}`, 100, yOffset);
    yOffset += 10;
    
    // Address Details
    doc.setFontSize(12);
    doc.text('Address Details', 14, yOffset);
    doc.setFontSize(10);
    yOffset += 6;
    doc.text(`Address: ${passenger.address || 'N/A'}`, 14, yOffset);
    yOffset += 6;
    doc.text(`City: ${passenger.city || 'N/A'}`, 14, yOffset);
    doc.text(`State: ${passenger.state || 'N/A'}`, 100, yOffset);
    yOffset += 6;
    doc.text(`Country: ${passenger.country || 'N/A'}`, 14, yOffset);
    doc.text(`Zip Code: ${passenger.zip_code || 'N/A'}`, 100, yOffset);

    yOffset += 20; // Add space before the next passenger's details
    if (index < selectedPassengers.length - 1) {
      doc.line(14, yOffset, 196, yOffset); // Add a separator line between profiles
      yOffset += 10;
    }
  });

  doc.save(`Passenger_Profiles_${today}.pdf`);
  message.success('PDF export successful!');
};
</script>

<style scoped>
/* Scoped styles for the new component */
</style>